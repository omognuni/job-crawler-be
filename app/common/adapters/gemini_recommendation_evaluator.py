from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Optional

from common.adapters.gemini_model_settings import get_gemini_model_name
from job.models import JobPosting
from recommendation.models import RecommendationPrompt
from resume.models import Resume

logger = logging.getLogger(__name__)


class GeminiRecommendationEvaluator:
    """
    Gemini 기반 추천 매칭 평가(배치) 어댑터.
    기존 `RecommendationService._evaluate_match_batch_with_llm` 로직을 인프라로 이동한 버전입니다.
    """

    def evaluate_batch(
        self,
        *,
        postings: list[JobPosting],
        resume: Resume,
        prompt: RecommendationPrompt,
        search_contexts: Optional[list[dict]] = None,
    ) -> list[dict]:
        def _default_result(reason: str) -> dict:
            return {"score": 50, "reason": reason}

        def _sanitize_score(value: Any) -> int:
            try:
                score = int(value)
            except Exception:
                return 50
            return min(100, max(0, score))

        def _normalize_item(value: Any) -> dict:
            if not isinstance(value, dict):
                return _default_result("LLM 응답 형식 오류")
            score = _sanitize_score(value.get("score"))
            reason = str(value.get("reason", "") or "").strip()
            if not reason:
                reason = "사유 미제공"
            # 너무 길면 저장/전송 비용이 커져서 제한합니다.
            if len(reason) > 300:
                reason = reason[:300].rstrip() + "…"
            return {"score": score, "reason": reason}

        def _strip_code_fences(text: str) -> str:
            t = (text or "").strip()
            # ```json ... ``` / ``` ... ``` 모두 방어
            if t.startswith("```"):
                t = re.sub(r"^```(?:json)?\s*\n", "", t, flags=re.IGNORECASE)
                t = re.sub(r"\n```$", "", t.strip())
            return t.strip()

        def _extract_json_from_text(text: str) -> Any:
            """
            Gemini가 JSON 외 설명/코드펜스를 섞어 반환하는 케이스를 방어합니다.
            - 1) 원문 그대로 json.loads 시도
            - 2) 코드펜스 제거 후 json.loads
            - 3) 첫 '[' ~ 마지막 ']' 범위만 잘라 json.loads (JSON list 우선)
            - 4) dict로 파싱되면 흔한 키(results/evaluations/items/data)에서 list를 추출
            """
            raw = (text or "").strip()
            if not raw:
                raise json.JSONDecodeError("Empty response", raw, 0)

            # 1) raw
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass

            # 2) strip fences
            cleaned = _strip_code_fences(raw)
            if cleaned and cleaned != raw:
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass

            # 3) bracket slice
            src = cleaned or raw
            start = src.find("[")
            end = src.rfind("]")
            if start != -1 and end != -1 and end > start:
                sliced = src[start : end + 1].strip()
                try:
                    return json.loads(sliced)
                except json.JSONDecodeError:
                    pass

            # 4) as dict then extract common list field
            start_obj = src.find("{")
            end_obj = src.rfind("}")
            if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
                sliced_obj = src[start_obj : end_obj + 1].strip()
                try:
                    obj = json.loads(sliced_obj)
                    if isinstance(obj, dict):
                        for key in ("results", "evaluations", "items", "data"):
                            val = obj.get(key)
                            if isinstance(val, list):
                                return val
                    return obj
                except json.JSONDecodeError:
                    pass

            # 마지막 fallback: 원래 에러를 유지하기 위해 재발생
            raise json.JSONDecodeError("Unparseable response", raw[:200], 0)

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("Google API key not found - using fallback")
            return [_default_result("API 키 미설정") for _ in postings]

        try:
            from google import genai
            from google.genai.errors import ClientError
            from google.genai.types import GenerateContentConfig

            client = genai.Client(api_key=api_key)

            resume_summary = resume.experience_summary or "이력서 내용 없음"
            analysis_result = resume.analysis_result or {}
            skills = (
                ", ".join(analysis_result.get("skills", []))
                if isinstance(analysis_result, dict)
                else ""
            )

            max_batch_size = 10
            if len(postings) > max_batch_size:
                postings = postings[:max_batch_size]
                if search_contexts:
                    search_contexts = search_contexts[:max_batch_size]

            jobs_text = ""
            for idx, posting in enumerate(postings):
                context_info = ""
                if search_contexts and idx < len(search_contexts):
                    ctx = search_contexts[idx]
                    # 근거/플랜 정보를 가능한 한 짧게 포함합니다(프롬프트 폭주 방지).
                    plan_summary = ""
                    if isinstance(ctx.get("plan"), dict):
                        p = ctx["plan"]
                        role = str(p.get("target_role", "") or "").strip()
                        rubric = (
                            p.get("scoring_rubric")
                            if isinstance(p.get("scoring_rubric"), dict)
                            else {}
                        )
                        plan_summary = f"\n- 타겟 역할: {role}\n- 루브릭: {json.dumps(rubric, ensure_ascii=False)}"

                    evidence_summary = ""
                    if isinstance(ctx.get("evidence_quotes"), list):
                        quotes = [
                            str(x) for x in ctx["evidence_quotes"] if str(x).strip()
                        ]
                        quotes = quotes[:4]
                        if quotes:
                            evidence_summary = "\n- 근거 스니펫:\n  - " + "\n  - ".join(
                                quotes
                            )

                    context_info = f"""
[Search Context - 이 공고는 다음 검색 기준으로 선별되었습니다]
- 벡터 유사도 점수: {ctx.get('vector_similarity', 0):.2f}
- 스킬 매칭 수: {ctx.get('skill_matches', 0)}개
- 하이브리드 점수: {ctx.get('hybrid_score', 0):.2f}
{plan_summary}{evidence_summary}
"""

                jobs_text += f"""
[Job {idx+1}]
ID: {posting.posting_id}
Company: {posting.company_name}
Position: {posting.position}
Main Tasks: {posting.main_tasks}
Requirements: {posting.requirements}
Preferred: {posting.preferred_points}{context_info}
-------------------
"""

            prompt_content = str(prompt.content or "").strip()
            if len(prompt_content) > 2000:
                logger.warning(
                    "RecommendationPrompt.content too long; truncating to 2000 chars"
                )
                prompt_content = prompt_content[:2000].rstrip() + "…"

            role_section = ""
            if prompt_content:
                # prompt.content가 "마크다운으로 출력" 같은 지시를 포함해도,
                # 아래 JSON 출력 요구사항이 항상 우선하도록 명시합니다.
                role_section = f"""
[Evaluator Role Instruction]
{prompt_content}

NOTE: The role instruction MUST NOT override the output format requirement below.
""".strip()

            full_prompt = f"""
{role_section}

[Candidate Resume Summary]
{resume_summary}
Skills: {skills}

[Job Postings - 벡터 유사도 검색 및 스킬 그래프 매칭을 통해 선별된 후보들]
{jobs_text}

Based on the resume, evaluate the candidate's fit for EACH job posting above.
Return a JSON list of objects, one for each job, in the same order.

Each object must have:
- score: Integer between 0 and 100
- reason: A concise explanation (1 sentence, Korean)

JSON Format Only:
[
  {{"score": 85, "reason": "..."}},
  {{"score": 40, "reason": "..."}}
]
""".strip()

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # 파싱 실패 시, 2~3번째 시도에서는 더 강하게 "JSON만"을 요구합니다.
                    attempt_prompt = full_prompt
                    if attempt > 0:
                        attempt_prompt = (
                            full_prompt
                            + "\n\n"
                            + "IMPORTANT: Output MUST be valid JSON only. "
                            + "Do NOT include markdown, code fences, or any extra text."
                        )
                    response = client.models.generate_content(
                        model=get_gemini_model_name(key="recommendation_evaluator"),
                        contents=attempt_prompt,
                        config=GenerateContentConfig(
                            temperature=0.1,
                            max_output_tokens=600,
                        ),
                    )
                    text = (response.text or "").strip()
                    if not text:
                        # safety block/빈 candidates 등으로 response.text가 비는 케이스를 진단하기 위한 정보
                        try:
                            candidates = getattr(response, "candidates", None)
                            prompt_feedback = getattr(response, "prompt_feedback", None)
                            logger.warning(
                                "Gemini evaluator returned empty text "
                                f"(candidates={candidates!r}, prompt_feedback={prompt_feedback!r})"
                            )
                        except Exception:
                            logger.warning(
                                "Gemini evaluator returned empty text (failed to inspect response)"
                            )
                    try:
                        parsed = _extract_json_from_text(text)
                    except (json.JSONDecodeError, ValueError) as e:
                        preview = (text or "").strip().replace("\n", "\\n")[:400]
                        logger.warning(
                            "Gemini evaluator JSON parse failed "
                            f"(attempt={attempt+1}/{max_retries}, preview={preview!r}): {e}"
                        )
                        raise

                    if not isinstance(parsed, list):
                        raise ValueError("LLM response is not a JSON list")

                    normalized = [_normalize_item(x) for x in parsed]
                    # 길이 불일치 방어: 부족하면 채우고, 넘치면 자릅니다.
                    if len(normalized) < len(postings):
                        normalized.extend(
                            [
                                _default_result("LLM 결과 부족")
                                for _ in range(len(postings) - len(normalized))
                            ]
                        )
                    return normalized[: len(postings)]
                except ClientError as e:
                    # 429 등 rate limit
                    if (
                        getattr(e, "status_code", None) == 429
                        and attempt < max_retries - 1
                    ):
                        wait = 2 * (attempt + 1)
                        logger.warning(
                            f"Gemini API Rate limit hit. Retrying in {wait}s..."
                        )
                        time.sleep(wait)
                        continue
                    raise
                except (json.JSONDecodeError, ValueError) as e:
                    if attempt < max_retries - 1:
                        continue
                    raise

            return [_default_result("LLM 분석 실패") for _ in postings]
        except Exception as e:
            logger.error(f"Batch LLM evaluation failed: {e}", exc_info=True)
            return [_default_result("LLM 분석 실패") for _ in postings]

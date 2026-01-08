from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional

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
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("Google API key not found - using fallback")
            return [{"score": 50, "reason": "API 키 미설정"} for _ in postings]

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
                    context_info = f"""
[Search Context - 이 공고는 다음 검색 기준으로 선별되었습니다]
- 벡터 유사도 점수: {ctx.get('vector_similarity', 0):.2f}
- 스킬 매칭 수: {ctx.get('skill_matches', 0)}개
- 하이브리드 점수: {ctx.get('hybrid_score', 0):.2f}
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

            full_prompt = f"""
{prompt.content}

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
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=full_prompt,
                        config=GenerateContentConfig(
                            temperature=0.1,
                            max_output_tokens=600,
                        ),
                    )
                    text = (response.text or "").strip()
                    text = re.sub(
                        r"^```json\\s*|\\s*```$", "", text, flags=re.MULTILINE
                    )
                    data = json.loads(text)
                    if not isinstance(data, list):
                        raise ValueError("LLM response is not a JSON list")
                    return data
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

            return [{"score": 50, "reason": "LLM 분석 실패"} for _ in postings]
        except Exception as e:
            logger.error(f"Batch LLM evaluation failed: {e}", exc_info=True)
            return [{"score": 50, "reason": "LLM 분석 실패"} for _ in postings]

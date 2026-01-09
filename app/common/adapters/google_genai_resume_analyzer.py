from __future__ import annotations

import json
import logging
import os
import re

from resume.dtos import ResumeAnalysisResultDTO

logger = logging.getLogger(__name__)


class GoogleGenAIResumeAnalyzer:
    """
    Google GenAI(Gemini) 기반 이력서 분석 어댑터.

    - 유스케이스에서 외부 SDK를 직접 import하지 않도록 분리합니다.
    - API 키 미설정/실패 시에도 항상 fallback 결과를 반환합니다.
    """

    def analyze(
        self,
        *,
        content: str,
        skills: list[str],
        inferred_position: str,
    ) -> ResumeAnalysisResultDTO:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("Google API key not found - using fallback")
            return ResumeAnalysisResultDTO(
                skills=skills,
                position=inferred_position,
                career_years=0,
                strengths="API 키 미설정으로 분석 불가",
                experience_summary=f"보유 스킬: {', '.join(skills[:10])}",
            )

        try:
            from google import genai
            from google.genai.types import GenerateContentConfig

            client = genai.Client(api_key=api_key)

            # 긴 이력서는 앞/뒤만 사용 (토큰/비용 관리)
            if len(content) > 5000:
                content_preview = (
                    content[:4000] + "\n\n[... 중간 생략 ...]\n\n" + content[-1000:]
                )
            else:
                content_preview = content

            prompt = f"""다음 이력서를 분석하여 JSON 형식으로 정보를 추출하세요.
이력서:
{content_preview}

요구사항:
1. career_years: 모든 경력 기간을 합산하여 총 경력 연차를 정수로 계산하세요.
   - 재직중인 경우 현재 날짜(2025년 11월)까지 계산
   - 소수점 이하는 반올림 (예: 1.8년 → 2년)
   - 경력이 없으면 0

2. strengths: 지원자의 핵심 강점을 한국어로 1-2줄로 요약 (50자 이내)
   - 주요 기술적 성과나 개선 사항 중심으로 요약

3. experience_summary: 이 지원자가 지원할 수 있는 '가상의 채용 공고' 내용을 작성하세요. (임베딩 검색용, 500자 이내)
   - 지원자의 모든 기술 스택(Python, Django, C++, Redis 등)을 포괄하는 공고 스타일로 작성
   - 예: "Python 및 Django 기반의 대용량 트래픽 처리 백엔드 개발자...", "C++ 및 Redis를 활용한 고성능 트레이딩 시스템 개발자..."
   - 다양한 직무 가능성을 열어두고 풍부한 키워드를 포함하세요.

4. position: 이 지원자에게 가장 어울리는 포지션을 추천하세요.
    - 지원자의 사용 언어, 프레임워크, 경험을 보고 판단
    - 추천할 만한 포지션이 없을 경우 빈 문자열
    - 예: "백엔드 개발자"

반드시 다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이 JSON만):
{{
  "career_years": 숫자,
  "position": "포지션",
  "strengths": "강점 설명",
  "experience_summary": "가상 채용 공고 내용"
}}
"""

            max_retries = 3
            parsed: dict | None = None
            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt,
                        config=GenerateContentConfig(
                            temperature=0.1,
                            max_output_tokens=400,
                        ),
                    )
                    result_text = (response.text or "").strip()
                    result_text = re.sub(
                        r"^```json\s*|\s*```$", "", result_text, flags=re.MULTILINE
                    )
                    parsed = json.loads(result_text)
                    break
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"JSON 파싱 실패 (시도 {attempt + 1}/{max_retries}): {e}. 재시도합니다."
                        )
                        continue
                    logger.error(f"JSON 파싱 최종 실패: {e}")
                    raise

            if not parsed:
                raise ValueError("LLM 응답 파싱 실패: 결과가 없습니다.")

            position_raw = parsed.get("position", "")
            if not isinstance(position_raw, str):
                position_raw = ""
            position = position_raw.strip() or inferred_position

            return ResumeAnalysisResultDTO(
                skills=skills,
                position=position,
                career_years=int(parsed.get("career_years", 0)),
                strengths=parsed.get("strengths", "분석 불가"),
                experience_summary=parsed.get(
                    "experience_summary",
                    f"경력 {parsed.get('career_years', 0)}년, {', '.join(skills[:5])} 경험",
                ),
            )
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}", exc_info=True)
            return ResumeAnalysisResultDTO(
                skills=skills,
                position=inferred_position,
                career_years=0,
                strengths=(
                    f"{', '.join(skills[:3])} 중심 경험"
                    if skills
                    else "이력서 분석 필요"
                ),
                experience_summary=f"보유 스킬: {', '.join(skills[:10])}",
            )

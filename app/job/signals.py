"""
이 파일은 하위 호환성을 위해 유지됩니다.
새로운 코드에서는 job.tasks 모듈의 Celery 태스크를 사용하세요.

- JobPosting 처리: job.tasks.process_job_posting
- Resume 처리: job.tasks.process_resume
- 스킬 추출: job.skill_extractor.extract_skills
"""

import json
import os
import re

from google import genai
from google.genai.types import GenerateContentConfig

# 검색할 기술 스택 목록 (대소문자 구분 없음)
# 이 목록은 하위 호환성을 위해 유지되지만, 새로운 코드에서는 skill_extractor.py 사용 권장
SKILL_LIST = [
    "Python",
    "Django",
    "Flask",
    "FastAPI",
    "JavaScript",
    "TypeScript",
    "React",
    "Vue.js",
    "Node.js",
    "Java",
    "Spring",
    "Kotlin",
    "Swift",
    "C++",
    "C#",
    "SQL",
    "NoSQL",
    "MySQL",
    "PostgreSQL",
    "MongoDB",
    "AWS",
    "GCP",
    "Azure",
    "Docker",
    "Kubernetes",
]


def _extract_career_years_regex(text: str) -> int:
    """정규표현식으로 경력 연차 추출 (Fallback)"""
    patterns = [
        r"경력[:\s]+(\d+)년",
        r"(\d+)년\s*경력",
        r"총\s*(\d+)년",
        r"(\d+)\+?\s*years?\s+(?:of\s+)?experience",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return 0


def _extract_resume_details(resume_content: str, skill_list: list[str]) -> dict:
    """LLM을 사용하여 이력서에서 기술 스택, 경력 연차, 강점을 추출합니다."""

    # 1. 먼저 규칙 기반으로 스킬 추출 (빠름)
    extracted_skills = _extract_skills_from_text(resume_content, skill_list)

    # 2. LLM을 사용하여 경력 연차와 강점 추출
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        # API 키가 없으면 Fallback
        return {
            "skills": extracted_skills,
            "career_years": _extract_career_years_regex(resume_content),
            "strengths": "API 키 미설정으로 분석 불가",
        }

    try:
        client = genai.Client(api_key=api_key)

        prompt = f"""다음 이력서를 분석하여 JSON 형식으로 정보를 추출하세요.
        이력서:
        {resume_content[:3000]}

        요구사항:
        1. career_years: 총 경력 연차를 정수로 추출 (예: 3, 5, 0). 경력이 명시되지 않으면 0
        2. strengths: 지원자의 핵심 강점을 한국어로 1-2줄로 요약 (50자 이내)

        반드시 다음 JSON 형식으로만 응답하세요:
        {{
        "career_years": 숫자,
        "strengths": "강점 설명"
        }}
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=200,
            ),
        )

        # JSON 파싱
        result_text = response.text.strip()
        # JSON 코드 블록 제거
        result_text = re.sub(
            r"^```json\s*|\s*```$", "", result_text, flags=re.MULTILINE
        )
        result = json.loads(result_text)

        career_years = int(result.get("career_years", 0))
        strengths = result.get("strengths", "분석 불가")

    except Exception as e:
        print(f"LLM 분석 실패: {e}")
        # Fallback: 정규표현식 시도
        career_years = _extract_career_years_regex(resume_content)
        strengths = (
            f"자동 분석: {', '.join(extracted_skills[:3])} 중심 경험"
            if extracted_skills
            else "이력서 분석 필요"
        )

    return {
        "skills": extracted_skills,
        "career_years": career_years,
        "strengths": strengths,
    }


# JobPosting 관련 시그널이 제거되었습니다.
# JobPosting 처리는 이제 Celery 태스크(job.tasks.process_job_posting)를 통해 비동기로 수행됩니다.
# models.py의 JobPosting.save()에서 자동으로 태스크를 호출합니다.

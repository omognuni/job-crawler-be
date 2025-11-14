import json
import os
import re

from common.graph_db import graph_db_client
from common.vector_db import vector_db_client
from django.db.models.signals import post_save
from django.dispatch import receiver
from google import genai
from google.genai.types import GenerateContentConfig

from .models import JobPosting

# 검색할 기술 스택 목록 (Fallback용 - LLM 실패 시에만 사용)
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


def _extract_skills_from_text(text: str, skill_list: list[str]) -> list[str]:
    """주어진 텍스트에서 기술 스택을 추출합니다. (Fallback용)"""
    found_skills = set()
    text_lower = text.lower()
    for skill in skill_list:
        if skill.lower() in text_lower:
            found_skills.add(skill)
    return sorted(list(found_skills))


def _extract_skills_with_llm(text: str, max_length: int = 2000) -> list[str]:
    """LLM을 사용하여 텍스트에서 기술 스택을 추출합니다."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return []

    try:
        client = genai.Client(api_key=api_key)

        prompt = f"""다음 텍스트에서 기술 스택(프로그래밍 언어, 프레임워크, 데이터베이스, 클라우드, 도구 등)만 추출하세요.

텍스트:
{text[:max_length]}

요구사항:
1. 정확한 기술명만 추출 (예: "Python", "Django", "AWS", "Docker")
2. 약어와 풀네임 모두 인식 (예: "JS" → "JavaScript")
3. 비슷한 이름 통합 (예: "Vue", "Vue.js" → "Vue.js")
4. 중복 제거
5. 최대 30개까지만 추출

반드시 다음 JSON 배열 형식으로만 응답하세요:
["Python", "Django", "Docker", "AWS"]
"""

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=300,
            ),
        )

        # JSON 파싱
        result_text = response.text.strip()
        # JSON 코드 블록 제거
        result_text = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", result_text, flags=re.MULTILINE
        )
        skills = json.loads(result_text)

        if isinstance(skills, list):
            return [str(skill) for skill in skills if skill]
        return []

    except Exception as e:
        print(f"[LLM 기술 스택 추출 실패] {e}")
        return []


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

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        # API 키가 없으면 Fallback
        return {
            "skills": _extract_skills_from_text(resume_content, skill_list),
            "career_years": _extract_career_years_regex(resume_content),
            "strengths": "API 키 미설정으로 분석 불가",
        }

    try:
        client = genai.Client(api_key=api_key)

        prompt = f"""다음 이력서를 분석하여 JSON 형식으로 정보를 추출하세요.
이력서:
{resume_content[:3000]}

요구사항:
1. skills: 보유한 모든 기술 스택을 배열로 추출 (예: ["Python", "Django", "Docker"])
   - 프로그래밍 언어, 프레임워크, 데이터베이스, 클라우드, 도구 등 모두 포함
   - 약어도 정확한 이름으로 변환 (예: "JS" → "JavaScript")
   - 최대 30개까지
2. career_years: 총 경력 연차를 정수로 추출 (예: 3, 5, 0). 경력이 명시되지 않으면 0
3. strengths: 지원자의 핵심 강점을 한국어로 1-2줄로 요약 (80자 이내)

반드시 다음 JSON 형식으로만 응답하세요:
{{
  "skills": ["Python", "Django", "Docker"],
  "career_years": 2,
  "strengths": "강점 설명"
}}
"""

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=500,
            ),
        )

        # JSON 파싱
        result_text = response.text.strip()
        # JSON 코드 블록 제거
        result_text = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", result_text, flags=re.MULTILINE
        )
        result = json.loads(result_text)

        skills = result.get("skills", [])
        career_years = int(result.get("career_years", 0))
        strengths = result.get("strengths", "분석 불가")

        # skills가 비어있으면 Fallback
        if not skills:
            skills = _extract_skills_from_text(resume_content, skill_list)

    except Exception as e:
        # LLM 실패 시 Fallback
        print(f"[LLM 이력서 분석 실패] {e}")
        skills = _extract_skills_from_text(resume_content, skill_list)
        career_years = _extract_career_years_regex(resume_content)
        strengths = (
            f"자동 분석: {', '.join(skills[:3])} 중심 경험"
            if skills
            else "이력서 분석 필요"
        )

    return {
        "skills": skills,
        "career_years": career_years,
        "strengths": strengths,
    }


@receiver(post_save, sender=JobPosting)
def embed_job_posting_on_save(sender, instance, created, **kwargs):
    """
    JobPosting 모델이 저장될 때 호출되어, 해당 공고의 정보를 벡터 DB와 그래프 DB에 저장합니다.
    """
    # --- 1. Vector DB에 임베딩 및 저장 ---
    collection = vector_db_client.get_or_create_collection("job_postings")

    document = f"""
    Position: {instance.position}
    Main Tasks: {instance.main_tasks}
    Requirements: {instance.requirements}
    Preferred Points: {instance.preferred_points}
    """

    vector_db_client.upsert_documents(
        collection=collection,
        documents=[document],
        metadatas=[
            {
                "company_name": instance.company_name,
                "location": instance.location,
                "employment_type": instance.employment_type,
                "career_min": instance.career_min,
                "career_max": instance.career_max,
            }
        ],
        ids=[str(instance.posting_id)],
    )
    # print(f"Successfully embedded job posting to Vector DB: {instance.posting_id}")

    # --- 2. JobPosting 모델에 skills_required 및 skills_preferred 저장 ---
    # LLM으로 기술 스택 추출 시도, 실패 시 규칙 기반 Fallback
    extracted_required_skills = _extract_skills_with_llm(instance.requirements)
    if not extracted_required_skills:
        extracted_required_skills = _extract_skills_from_text(
            instance.requirements, SKILL_LIST
        )

    extracted_preferred_skills = _extract_skills_with_llm(instance.preferred_points)
    if not extracted_preferred_skills:
        extracted_preferred_skills = _extract_skills_from_text(
            instance.preferred_points, SKILL_LIST
        )

    # 변경 사항이 있을 경우에만 업데이트
    if (
        instance.skills_required != extracted_required_skills
        or instance.skills_preferred != extracted_preferred_skills
    ):
        instance.skills_required = extracted_required_skills
        instance.skills_preferred = extracted_preferred_skills
        instance.save(update_fields=["skills_required", "skills_preferred"])
        # print(
        #     f"Updated skills for job posting {instance.posting_id}: "
        #     f"Required={instance.skills_required}, Preferred={instance.skills_preferred}"
        # )

    # --- 3. Graph DB에 엔티티 및 관계 저장 ---
    # Vector DB와 JobPosting 모델에 저장된 스킬을 합쳐서 Graph DB에 저장
    all_extracted_skills = list(
        set(extracted_required_skills + extracted_preferred_skills)
    )

    if all_extracted_skills:
        graph_db_client.add_job_posting(
            posting_id=instance.posting_id,
            position=instance.position,
            company_name=instance.company_name,
            skills=all_extracted_skills,
        )
        # print(
        #     f"Successfully saved job posting to Graph DB: {instance.posting_id} with skills: {all_extracted_skills}"
        # )

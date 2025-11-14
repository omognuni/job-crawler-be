from common.graph_db import graph_db_client
from common.vector_db import vector_db_client
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import JobPosting

# 검색할 기술 스택 목록 (대소문자 구분 없음)
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
    """주어진 텍스트에서 기술 스택을 추출합니다."""
    found_skills = set()
    text_lower = text.lower()
    for skill in skill_list:
        if skill.lower() in text_lower:
            found_skills.add(skill)
    return sorted(list(found_skills))


def _extract_resume_details(resume_content: str, skill_list: list[str]) -> dict:
    """이력서 내용에서 기술 스택, 경력 연차, 강점 등을 추출합니다."""
    extracted_skills = _extract_skills_from_text(resume_content, skill_list)

    # TODO: Implement more sophisticated extraction for career_years and strengths
    # For now, these will be placeholders or require LLM for initial population
    career_years = 0  # Placeholder
    strengths = "이력서에서 추출된 강점 (LLM 또는 고급 추출 필요)"  # Placeholder

    return {
        "skills": extracted_skills,
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
    extracted_required_skills = _extract_skills_from_text(
        instance.requirements, SKILL_LIST
    )
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

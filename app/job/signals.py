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


def _extract_skills(instance: JobPosting, skill_list: list[str]) -> set[str]:
    """채용 공고 내용에서 기술 스택을 추출합니다."""
    content = (
        f"{instance.main_tasks} {instance.requirements} {instance.preferred_points}"
    ).lower()

    found_skills = set()
    for skill in skill_list:
        if skill.lower() in content:
            found_skills.add(skill)
    return found_skills


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
    print(f"Successfully embedded job posting to Vector DB: {instance.posting_id}")

    # --- 2. Graph DB에 엔티티 및 관계 저장 ---
    skills = _extract_skills(instance, SKILL_LIST)

    if skills:
        graph_db_client.add_job_posting(
            posting_id=instance.posting_id,
            position=instance.position,
            company_name=instance.company_name,
            skills=list(skills),
        )
        print(
            f"Successfully saved job posting to Graph DB: {instance.posting_id} with skills: {skills}"
        )

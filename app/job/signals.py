from common.vector_db import vector_db_client
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import JobPosting


@receiver(post_save, sender=JobPosting)
def embed_job_posting_on_save(sender, instance, created, **kwargs):
    """
    JobPosting 모델이 저장될 때 호출되어, 해당 공고의 정보를 벡터 DB에 임베딩하고 저장합니다.
    """
    collection = vector_db_client.get_or_create_collection("job_postings")

    # 임베딩할 문서 내용 조합
    document = f"""
    Position: {instance.position}
    Main Tasks: {instance.main_tasks}
    Requirements: {instance.requirements}
    Preferred Points: {instance.preferred_points}
    """

    # 벡터 DB에 저장
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
    print(f"Successfully embedded job posting: {instance.posting_id}")

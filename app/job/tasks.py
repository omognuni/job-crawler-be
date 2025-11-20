"""
Celery 태스크: 채용 공고 및 이력서 처리
"""

from celery import shared_task
from common.graph_db import graph_db_client
from common.vector_db import vector_db_client
from job.models import JobPosting
from skill.services import extract_skills_from_job_posting


@shared_task(bind=True, max_retries=3)
def process_job_posting(self, posting_id: int):
    """
    채용 공고를 처리하는 Celery 태스크

    1. posting_id로 JobPosting 조회
    2. skill_extractor로 스킬 추출 → skills_required, skills_preferred 업데이트
    3. 임베딩 벡터 생성 (position + main_tasks + requirements)
    4. ChromaDB 'job_postings' 컬렉션에 upsert
    5. Neo4j에 (JobPosting)-[:REQUIRES_SKILL]->(Skill) 관계 생성

    Args:
        posting_id: JobPosting의 ID

    Returns:
        dict: 처리 결과
    """
    try:
        # 1. JobPosting 조회
        try:
            job_posting = JobPosting.objects.get(posting_id=posting_id)
        except JobPosting.DoesNotExist:
            error_msg = f"JobPosting {posting_id} not found"
            print(f"[ERROR] {error_msg}")
            return {"success": False, "error": error_msg}

        # 2. 스킬 추출
        skills_required, skills_preferred = extract_skills_from_job_posting(
            requirements=job_posting.requirements,
            preferred_points=job_posting.preferred_points,
            main_tasks=job_posting.main_tasks,
        )

        # skills_required와 skills_preferred 업데이트 (변경이 있을 경우에만)
        if (
            job_posting.skills_required != skills_required
            or job_posting.skills_preferred != skills_preferred
        ):
            job_posting.skills_required = skills_required
            job_posting.skills_preferred = skills_preferred
            job_posting.save(update_fields=["skills_required", "skills_preferred"])
            print(
                f"[INFO] Updated skills for posting {posting_id}: "
                f"Required={len(skills_required)}, Preferred='{skills_preferred[:50]}...'"
            )

        # 3. 임베딩 텍스트 생성 (노이즈 제거)
        # 회사 소개, 위치, 복지 등을 제외하고 핵심 정보만 임베딩
        embedding_text = f"""
Position: {job_posting.position or 'N/A'}
Main Tasks: {job_posting.main_tasks or 'N/A'}
Requirements: {job_posting.requirements or 'N/A'}
Preferred Points: {job_posting.preferred_points or 'N/A'}
        """.strip()

        # 4. ChromaDB에 upsert (텍스트가 충분히 긴 경우에만)
        if len(embedding_text) > 10:  # 최소 길이 체크
            try:
                collection = vector_db_client.get_or_create_collection("job_postings")
                vector_db_client.upsert_documents(
                    collection=collection,
                    documents=[embedding_text],
                    metadatas=[
                        {
                            "company_name": job_posting.company_name or "",
                            "location": job_posting.location or "",
                            "employment_type": job_posting.employment_type or "",
                            "career_min": job_posting.career_min,
                            "career_max": job_posting.career_max,
                        }
                    ],
                    ids=[str(posting_id)],
                )
                print(f"[INFO] Embedded job posting {posting_id} to Vector DB")
            except Exception as e:
                print(
                    f"[WARNING] Failed to embed posting {posting_id} to Vector DB: {str(e)}"
                )
                # ChromaDB 실패는 치명적이지 않으므로 계속 진행
        else:
            print(
                f"[WARNING] Skipping embedding for posting {posting_id}: text too short"
            )

        # 5. Neo4j에 관계 생성 (필수 스킬만)
        if skills_required:
            graph_db_client.add_job_posting(
                posting_id=posting_id,
                position=job_posting.position,
                company_name=job_posting.company_name,
                skills=skills_required,
            )
            print(
                f"[INFO] Saved job posting {posting_id} to Graph DB with {len(skills_required)} required skills"
            )

        return {
            "success": True,
            "posting_id": posting_id,
            "skills_required": len(skills_required),
            "skills_preferred_text": skills_preferred[:50] if skills_preferred else "",
        }

    except Exception as e:
        error_msg = f"Error processing job posting {posting_id}: {str(e)}"
        print(f"[ERROR] {error_msg}")

        # 재시도
        try:
            raise self.retry(exc=e, countdown=60)  # 60초 후 재시도
        except self.MaxRetriesExceededError:
            print(f"[ERROR] Max retries exceeded for posting {posting_id}")
            return {"success": False, "error": error_msg}

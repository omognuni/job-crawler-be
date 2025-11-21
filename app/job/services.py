"""
Job Posting Service

채용 공고 관리 및 처리 서비스
"""

import logging
from typing import Dict, List, Optional

from common.graph_db import graph_db_client
from common.vector_db import vector_db_client
from django.db import transaction
from job.models import JobPosting
from skill.services import SkillExtractionService

logger = logging.getLogger(__name__)


class JobService:
    """
    채용 공고 서비스

    채용 공고의 CRUD 및 처리 로직을 담당합니다.
    """

    @staticmethod
    def get_job_posting(posting_id: int) -> Optional[JobPosting]:
        """
        채용 공고 조회

        Args:
            posting_id: 채용 공고 ID

        Returns:
            JobPosting 객체 또는 None
        """
        try:
            return JobPosting.objects.get(posting_id=posting_id)
        except JobPosting.DoesNotExist:
            logger.warning(f"JobPosting {posting_id} not found")
            return None

    @staticmethod
    def get_all_job_postings() -> List[JobPosting]:
        """
        모든 채용 공고 조회

        Returns:
            JobPosting 쿼리셋
        """
        return JobPosting.objects.all()

    @staticmethod
    def create_job_posting(data: Dict) -> JobPosting:
        """
        채용 공고 생성

        Args:
            data: 채용 공고 데이터 딕셔너리

        Returns:
            생성된 JobPosting 객체
        """
        with transaction.atomic():
            job_posting = JobPosting.objects.create(**data)
            logger.info(f"Created JobPosting {job_posting.posting_id}")
            return job_posting

    @staticmethod
    def update_job_posting(posting_id: int, data: Dict) -> Optional[JobPosting]:
        """
        채용 공고 업데이트

        Args:
            posting_id: 채용 공고 ID
            data: 업데이트할 데이터 딕셔너리

        Returns:
            업데이트된 JobPosting 객체 또는 None
        """
        job_posting = JobService.get_job_posting(posting_id)
        if not job_posting:
            return None

        with transaction.atomic():
            for key, value in data.items():
                setattr(job_posting, key, value)
            job_posting.save()
            logger.info(f"Updated JobPosting {posting_id}")
            return job_posting

    @staticmethod
    def delete_job_posting(posting_id: int) -> bool:
        """
        채용 공고 삭제

        Args:
            posting_id: 채용 공고 ID

        Returns:
            삭제 성공 여부
        """
        job_posting = JobService.get_job_posting(posting_id)
        if not job_posting:
            return False

        with transaction.atomic():
            job_posting.delete()
            logger.info(f"Deleted JobPosting {posting_id}")
            return True

    @staticmethod
    def process_job_posting_sync(posting_id: int) -> Dict:
        """
        채용 공고 처리 (동기 방식)

        스킬 추출, 임베딩 생성, Graph DB 저장을 수행합니다.
        Celery 작업에서 호출되거나, 테스트/관리 명령에서 직접 호출됩니다.

        Args:
            posting_id: 채용 공고 ID

        Returns:
            처리 결과 딕셔너리
        """
        try:
            # 1. JobPosting 조회
            job_posting = JobService.get_job_posting(posting_id)
            if not job_posting:
                error_msg = f"JobPosting {posting_id} not found"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # 2. 스킬 추출
            skills_required, skills_preferred = (
                SkillExtractionService.extract_skills_from_job_posting(
                    requirements=job_posting.requirements,
                    preferred_points=job_posting.preferred_points,
                    main_tasks=job_posting.main_tasks,
                )
            )

            # 스킬 업데이트 (변경이 있을 경우에만)
            if (
                job_posting.skills_required != skills_required
                or job_posting.skills_preferred != skills_preferred
            ):
                job_posting.skills_required = skills_required
                job_posting.skills_preferred = skills_preferred
                job_posting.save(update_fields=["skills_required", "skills_preferred"])
                logger.info(
                    f"Updated skills for posting {posting_id}: "
                    f"Required={len(skills_required)}, Preferred='{skills_preferred[:50]}...'"
                )

            # 3. 임베딩 텍스트 생성 (노이즈 제거)
            embedding_text = f"""
Position: {job_posting.position or 'N/A'}
Main Tasks: {job_posting.main_tasks or 'N/A'}
Requirements: {job_posting.requirements or 'N/A'}
Preferred Points: {job_posting.preferred_points or 'N/A'}
            """.strip()

            # 4. ChromaDB에 upsert
            if len(embedding_text) > 10:
                try:
                    collection = vector_db_client.get_or_create_collection(
                        "job_postings"
                    )
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
                    logger.info(f"Embedded job posting {posting_id} to Vector DB")
                except Exception as e:
                    logger.warning(
                        f"Failed to embed posting {posting_id} to Vector DB: {str(e)}"
                    )

            # 5. Neo4j에 관계 생성
            if skills_required:
                graph_db_client.add_job_posting(
                    posting_id=posting_id,
                    position=job_posting.position,
                    company_name=job_posting.company_name,
                    skills=skills_required,
                )
                logger.info(
                    f"Saved job posting {posting_id} to Graph DB with {len(skills_required)} skills"
                )

            return {
                "success": True,
                "posting_id": posting_id,
                "skills_required": len(skills_required),
                "skills_preferred_text": (
                    skills_preferred[:50] if skills_preferred else ""
                ),
            }

        except Exception as e:
            error_msg = f"Error processing job posting {posting_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

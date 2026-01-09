"""
Job Posting Service

채용 공고 관리 및 처리 서비스
"""

import logging
from typing import Dict, List, Optional

from django.db import transaction
from job.models import JobPosting

logger = logging.getLogger(__name__)

from common.application.result import Err, Ok
from job.application.container import build_process_job_posting_usecase
from job.dtos import ProcessJobPostingResultDTO


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
    def get_all_job_postings(query_params: Dict) -> List[JobPosting]:
        """
        모든 채용 공고 조회

        Returns:
            JobPosting 쿼리셋
        """

        filters = {}

        if start_date := query_params.get("start_date"):
            filters["created_at__gte"] = start_date

        if end_date := query_params.get("end_date"):
            filters["created_at__lte"] = end_date

        if career_min := query_params.get("career_min"):
            filters["career_min"] = career_min

        if career_max := query_params.get("career_max"):
            filters["career_max"] = career_max

        queryset = JobPosting.objects.filter(**filters).order_by("-created_at")
        return queryset

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
    def process_job_posting_sync(posting_id: int, reindex: bool = False) -> Dict:
        """
        채용 공고 처리 (동기 방식)

        스킬 추출, 임베딩 생성, Graph DB 저장을 수행합니다.
        Celery 작업에서 호출되거나, 테스트/관리 명령에서 직접 호출됩니다.

        Args:
            posting_id: 채용 공고 ID
            reindex: 강제 재인덱싱 여부 (현재는 로직 차이 없음)

        Returns:
            처리 결과 딕셔너리
        """
        usecase = build_process_job_posting_usecase()
        result = usecase.execute(posting_id=posting_id)
        if isinstance(result, Ok):
            dto: ProcessJobPostingResultDTO = result.value
            return dto.model_dump()
        assert isinstance(result, Err)
        return {"success": False, "error": result.message}

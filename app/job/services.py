"""
Job Posting Service

채용 공고 관리 및 처리 서비스
"""

import logging
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
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

        queryset = JobPosting.objects.all()

        # --- 날짜/기간 필터 (기존 + 신규) ---
        # 기존(start_date/end_date): DateField 기반
        if start_date := query_params.get("start_date"):
            start_dt = timezone.make_aware(datetime.combine(start_date, time.min))
            queryset = queryset.filter(created_at__gte=start_dt)

        if end_date := query_params.get("end_date"):
            end_dt = timezone.make_aware(datetime.combine(end_date, time.max))
            queryset = queryset.filter(created_at__lte=end_dt)

        # 신규(days/posted_after)
        if query_params.get("days") is not None:
            days = query_params["days"]
            since = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=since)

        if posted_after := query_params.get("posted_after"):
            posted_after_dt = timezone.make_aware(
                datetime.combine(posted_after, time.min)
            )
            queryset = queryset.filter(created_at__gte=posted_after_dt)

        # --- 경력 필터 ---
        # 기존(career_min/career_max): 기존 동작 유지(정확 일치)
        if query_params.get("career_min") is not None:
            queryset = queryset.filter(career_min=query_params["career_min"])

        if query_params.get("career_max") is not None:
            queryset = queryset.filter(career_max=query_params["career_max"])

        # 신규(experience): candidate years가 posting 범위에 포함되는 공고만
        if query_params.get("experience") is not None:
            experience = query_params["experience"]
            queryset = queryset.filter(
                Q(career_min__isnull=True) | Q(career_min__lte=experience)
            ).filter(Q(career_max__isnull=True) | Q(career_max__gte=experience))

        # --- 텍스트/필드 필터 ---
        if company := query_params.get("company"):
            queryset = queryset.filter(company_name__icontains=company)

        if location := query_params.get("location"):
            queryset = queryset.filter(location__icontains=location)

        if district := query_params.get("district"):
            queryset = queryset.filter(district__icontains=district)

        # source: 모델에 별도 필드가 없어서 url 부분 매칭으로 지원(수집 소스 구분)
        if source := query_params.get("source"):
            queryset = queryset.filter(url__icontains=source)

        if q := query_params.get("q"):
            queryset = queryset.filter(
                Q(company_name__icontains=q)
                | Q(position__icontains=q)
                | Q(main_tasks__icontains=q)
                | Q(requirements__icontains=q)
                | Q(preferred_points__icontains=q)
                | Q(location__icontains=q)
                | Q(district__icontains=q)
            )

        # tech_stack: skills_required(JSON 배열) 기반으로 필터링.
        # DB 백엔드별 JSON contains 지원 편차를 피하기 위해 Python 레벨로 안전하게 처리.
        tech_stack: list[str] = query_params.get("tech_stack") or []
        materialized: Optional[list[JobPosting]] = None
        if tech_stack:
            materialized = list(queryset)
            normalized = [s.strip() for s in tech_stack if s and s.strip()]
            if normalized:
                materialized = [
                    jp
                    for jp in materialized
                    if jp.skills_required
                    and any(stack in jp.skills_required for stack in normalized)
                ]

        # --- 정렬 ---
        sort = query_params.get("sort") or "latest"
        if materialized is None:
            if sort == "oldest":
                return queryset.order_by("created_at")
            return queryset.order_by("-created_at")

        # list 정렬(Python)
        reverse = sort != "oldest"
        return sorted(materialized, key=lambda jp: jp.created_at, reverse=reverse)

    @staticmethod
    def get_company_options(*, q: str = "", limit: int = 20) -> list[str]:
        """
        회사명 옵션 목록(typeahead) 조회.

        Args:
            q: 회사명 부분 문자열(대소문자 무시)
            limit: 반환 최대 개수(상한은 serializer에서 제한)
        """
        qs = (
            JobPosting.objects.exclude(company_name__isnull=True)
            .exclude(company_name="")
            .values_list("company_name", flat=True)
        )
        if q:
            qs = qs.filter(company_name__icontains=q)

        # DISTINCT + 정렬
        return list(qs.distinct().order_by("company_name")[:limit])

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

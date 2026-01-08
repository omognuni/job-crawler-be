"""
Resume Celery Tasks

이력서 비동기 처리 태스크
"""

import logging

from celery import shared_task
from common.application.result import Err, Ok
from resume.application.container import build_process_resume_usecase

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_resume(self, resume_id: int, force_reindex: bool = False):
    """
    이력서를 처리하는 Celery 태스크

    ResumeService를 통해 분석, 임베딩 생성을 수행합니다.

    Args:
        resume_id: Resume ID
        force_reindex: 강제 재임베딩 여부 (True면 LLM 분석 생략, 임베딩만 수행)

    Returns:
        dict: 처리 결과
    """
    try:
        usecase = build_process_resume_usecase()

        # force_reindex=True는 "분석 스킵"이 아니라 "임베딩 재생성" 목적이었는데,
        # 현재 서비스 구현은 필드 누락 시 분석을 수행하는 등 정책이 섞여 있었습니다.
        # 새 정책: force_reindex=True => 분석은 하지 않고 임베딩만 갱신(run_analysis=False)
        # (필요하면 추후 옵션을 분리: force_analysis/force_embedding 등)
        result = usecase.execute(
            resume_id=int(resume_id),
            run_analysis=not force_reindex,
        )

        if isinstance(result, Ok):
            return result.value.model_dump()

        assert isinstance(result, Err)

        # NOT_FOUND / VALIDATION_ERROR 는 재시도해도 의미가 없으므로 즉시 실패 반환
        if result.code in {"NOT_FOUND", "VALIDATION_ERROR"}:
            return {"success": False, "error": result.message}

        # 그 외는 일시적 실패 가능성이 있어 재시도
        raise self.retry(exc=Exception(result.message), countdown=60)

    except Exception as e:
        error_msg = f"Error processing resume {resume_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # 재시도
        try:
            raise self.retry(exc=e, countdown=60)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for resume {resume_id}")
            return {"success": False, "error": error_msg}

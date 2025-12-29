"""
Resume Celery Tasks

이력서 비동기 처리 태스크
"""

import logging

from celery import shared_task
from resume.services import ResumeService

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
        # ResumeService에 위임
        result = ResumeService.process_resume_sync(
            resume_id=resume_id, force_reindex=force_reindex
        )

        if not result.success:
            # 처리 실패 시 재시도
            error = Exception(result.error or "Unknown error")
            raise self.retry(exc=error, countdown=60)

        return result.model_dump()

    except Exception as e:
        error_msg = f"Error processing resume {resume_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # 재시도
        try:
            raise self.retry(exc=e, countdown=60)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for resume {resume_id}")
            return {"success": False, "error": error_msg}

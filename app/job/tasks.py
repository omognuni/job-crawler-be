"""
Celery 태스크: 채용 공고 처리
"""

import logging

from celery import shared_task
from job.services import JobService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_job_posting(self, posting_id: int):
    """
    채용 공고를 처리하는 Celery 태스크

    JobService를 통해 스킬 추출, 임베딩 생성, Graph DB 저장을 수행합니다.

    Args:
        posting_id: JobPosting의 ID

    Returns:
        dict: 처리 결과
    """
    try:
        # JobService에 위임
        result = JobService.process_job_posting_sync(posting_id)

        if not result.get("success"):
            # 처리 실패 시 재시도
            error = Exception(result.get("error", "Unknown error"))
            raise self.retry(exc=error, countdown=60)

        return result

    except Exception as e:
        error_msg = f"Error processing job posting {posting_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # 재시도
        try:
            raise self.retry(exc=e, countdown=60)  # 60초 후 재시도
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for posting {posting_id}")
            return {"success": False, "error": error_msg}

"""
Celery 태스크: 채용 공고 처리
"""

import logging

from celery import shared_task
from common.application.result import Err, Ok
from job.application.container import build_process_job_posting_usecase
from job.dtos import ProcessJobPostingResultDTO

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_job_posting(self, posting_id: int, reindex: bool = False):
    """
    채용 공고를 처리하는 Celery 태스크

    JobService를 통해 스킬 추출, 임베딩 생성, Graph DB 저장을 수행합니다.

    Args:
        posting_id: JobPosting의 ID
        reindex: 강제 재인덱싱 여부

    Returns:
        dict: 처리 결과
    """
    try:
        # reindex는 현재 로직 차이 없음(유지)
        usecase = build_process_job_posting_usecase()
        result = usecase.execute(posting_id=int(posting_id))

        if isinstance(result, Ok):
            dto: ProcessJobPostingResultDTO = result.value
            return dto.model_dump()

        assert isinstance(result, Err)
        if result.code == "NOT_FOUND":
            return {"success": False, "error": result.message}

        raise self.retry(exc=Exception(result.message), countdown=60)

    except Exception as e:
        error_msg = f"Error processing job posting {posting_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # 재시도
        try:
            raise self.retry(exc=e, countdown=60)  # 60초 후 재시도
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for posting {posting_id}")
            return {"success": False, "error": error_msg}

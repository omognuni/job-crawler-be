"""
Job Posting Celery Tasks

채용 공고 비동기 처리 태스크
"""

from celery import shared_task

# TODO: job/tasks.py에서 process_job_posting 태스크 이동 예정
# @shared_task(bind=True, max_retries=3, name='job_posting.process_job_posting')
# def process_job_posting(self, posting_id: int):
#     """
#     채용 공고를 처리하는 Celery 태스크
#
#     1. 스킬 추출
#     2. 임베딩 생성
#     3. ChromaDB 저장
#     4. Neo4j 관계 생성
#     """
#     pass

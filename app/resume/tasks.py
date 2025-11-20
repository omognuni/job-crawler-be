"""
Resume Celery Tasks

이력서 비동기 처리 태스크
"""

from celery import shared_task

# TODO: job/tasks.py에서 process_resume 태스크 이동 예정
# @shared_task(bind=True, max_retries=3, name='resume.process_resume')
# def process_resume(self, user_id: int):
#     """
#     이력서를 처리하는 Celery 태스크
#
#     1. needs_analysis() 체크
#     2. 스킬 추출 (LLM-Free)
#     3. LLM 호출 (경력, 강점, 요약)
#     4. Resume 업데이트
#     5. ChromaDB 임베딩
#     """
#     pass

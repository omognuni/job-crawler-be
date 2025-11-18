"""
CrewAI 기반 Job Hunter Crew

⚠️ DEPRECATED: 이 모듈은 더 이상 추천 시스템에 사용되지 않습니다.

추천 시스템은 AI-Free 실시간 추천 엔진(job/recommender.py)으로 대체되었습니다.
- 응답 속도: 0.1초 이내 (기존 대비 95% 개선)
- AI 비용: 95% 절감
- 매칭 정확도: 벡터 유사도 + 스킬 그래프 하이브리드 방식

이 파일은 향후 다른 AI 기능을 위해 유지되지만, 추천 기능은 사용하지 않습니다.
새로운 추천 API: /api/job/recommendations/for-user/<user_id>/
"""

import os

from agent.agents import JobAgents
from agent.tasks import JobTasks
from crewai import Crew, CrewOutput


class JobHunterCrew:
    """
    [DEPRECATED] CrewAI 기반 채용 공고 추천 크루

    새로운 추천 시스템을 사용하세요:
    - job.recommender.get_recommendations(user_id, limit=10)
    - API: GET /api/job/recommendations/for-user/<user_id>/
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.agents = JobAgents()
        self.tasks = JobTasks()
        self._validate_api_keys()

    def _validate_api_keys(self):
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다.")

    def run(self) -> CrewOutput:
        """
        [DEPRECATED] CrewAI 기반 추천 실행

        이 메서드는 더 이상 사용되지 않습니다.
        대신 job.recommender.get_recommendations()를 사용하세요.
        """
        # 에이전트 생성
        resume_inspector = self.agents.resume_inspector()
        job_posting_inspector = self.agents.job_posting_inspector()
        job_hunter = self.agents.job_hunter()

        # 태스크 생성
        analyze_resume = self.tasks.analyze_resume_task(self.user_id)
        fetch_job_postings = self.tasks.fetch_job_postings_task()
        recommend_jobs = self.tasks.recommend_jobs_task(self.user_id)

        # 컨텍스트 설정
        fetch_job_postings.context = [analyze_resume]
        recommend_jobs.context = [analyze_resume, fetch_job_postings]

        # 크루 생성
        crew = Crew(
            agents=[resume_inspector, job_posting_inspector, job_hunter],
            tasks=[analyze_resume, fetch_job_postings, recommend_jobs],
            verbose=True,
        )

        # 크루 실행
        result = crew.kickoff()
        print("--- Agent's Raw Output ---")
        print(result.raw)
        print("--------------------------")
        return result

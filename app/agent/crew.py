from agent.agents import JobAgents
from agent.tasks import JobTasks
from crewai import Crew, CrewOutput


class JobHunterCrew:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.agents = JobAgents()
        self.tasks = JobTasks()

    def run(self) -> CrewOutput:
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

import os
from crewai import Agent, Task, Crew, LLM
from crewai.project import CrewBase, agent, crew, task
from django.utils import timezone
from app.agent.models import JobPosting, Resume, JobRecommendation
from typing import Annotated
import json


class JobHunterCrew(CrewBase):
    agents: list[Agent] = []
    crews: list[Crew] = []
    tasks: list[Task] = []

    def __init__(self, user_id: int = 1):
        super().__init__()
        self.user_id = user_id
        self._validate_api_keys()
    
    def _validate_api_keys(self):
        """LLM API 키가 설정되어 있는지 확인"""
        openai_key = os.getenv("OPENAI_API_KEY")
        google_key = os.getenv("GOOGLE_API_KEY")
        
        if not openai_key:
            raise ValueError(
                "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다. "
                "환경 변수를 설정하거나 .env 파일을 추가하세요."
            )
        
        if not google_key:
            raise ValueError(
                "GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. "
                "환경 변수를 설정하거나 .env 파일을 추가하세요."
            )

    # ===== Tools (Function calling) =====
    def fetch_job_postings_tool(self) -> str:
        """
        데이터베이스에서 모든 채용 공고를 조회합니다.
        
        Returns:
            JSON 문자열: 모든 채용 공고 목록
        """
        job_postings = JobPosting.objects.all().values(
            'posting_id', 'url', 'company_name', 'position',
            'main_tasks', 'requirements', 'preferred_points',
            'location', 'district', 'employment_type',
            'career_min', 'career_max'
        )
        return json.dumps(list(job_postings), ensure_ascii=False, default=str)

    def get_resume_tool(
        self, 
        user_id: Annotated[int, "조회할 사용자의 ID"]
    ) -> str:
        """
        사용자의 이력서를 조회하고, 필요시 분석합니다.
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            JSON 문자열: 이력서 내용과 분석 결과
        """
        try:
            resume = Resume.objects.get(user_id=user_id)
            
            if resume.needs_analysis():
                return json.dumps({
                    'status': 'needs_analysis',
                    'user_id': resume.user_id,
                    'content': resume.content,
                    'message': '이력서 분석이 필요합니다. analyze_resume_tool을 사용하세요.'
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    'status': 'cached',
                    'user_id': resume.user_id,
                    'content': resume.content,
                    'analysis_result': resume.analysis_result,
                    'analyzed_at': str(resume.analyzed_at)
                }, ensure_ascii=False, default=str)
        except Resume.DoesNotExist:
            return json.dumps({
                'status': 'error',
                'message': f'User {user_id}의 이력서를 찾을 수 없습니다.'
            }, ensure_ascii=False)

    def analyze_resume_tool(
        self, 
        user_id: Annotated[int, "사용자 ID"],
        analysis_result: Annotated[dict, "분석 결과 딕셔너리 (skills, experiences, strengths, career_years, preferred_areas 포함)"]
    ) -> str:
        """
        이력서 분석 결과를 저장합니다.
        
        Args:
            user_id: 사용자 ID
            analysis_result: 분석 결과 딕셔너리 (skills, experiences, strengths, career_years, preferred_areas 포함)
            
        Returns:
            JSON 문자열: 저장된 분석 결과
        """
        try:
            resume = Resume.objects.get(user_id=user_id)
            resume.analysis_result = analysis_result
            resume.analyzed_at = timezone.now()
            resume.save()
            
            return json.dumps({
                'status': 'success',
                'user_id': user_id,
                'analysis_result': analysis_result,
                'analyzed_at': str(resume.analyzed_at)
            }, ensure_ascii=False, default=str)
        except Resume.DoesNotExist:
            return json.dumps({
                'status': 'error',
                'message': f'User {user_id}의 이력서를 찾을 수 없습니다.'
            }, ensure_ascii=False)

    def save_recommendations_tool(
        self, 
        user_id: Annotated[int, "사용자 ID"],
        recommendations: Annotated[list, "추천 목록 (각 항목은 posting_id, rank, match_score, match_reason 포함)"]
    ) -> str:
        """
        Top 10 추천 공고를 데이터베이스에 저장합니다.
        
        Args:
            user_id: 사용자 ID
            recommendations: 추천 목록 (각 항목은 posting_id, rank, match_score, match_reason 포함)
            
        Returns:
            JSON 문자열: 저장 결과
        """
        saved_recommendations = []
        
        for rec in recommendations[:10]:  # Top 10만 저장
            try:
                job_posting = JobPosting.objects.get(posting_id=rec['posting_id'])
                
                recommendation = JobRecommendation.objects.create(
                    user_id=user_id,
                    job_posting=job_posting,
                    rank=rec['rank'],
                    match_score=rec['match_score'],
                    match_reason=rec['match_reason']
                )
                
                saved_recommendations.append({
                    'id': recommendation.id,
                    'rank': recommendation.rank,
                    'posting_id': rec['posting_id'],
                    'company_name': job_posting.company_name,
                    'position': job_posting.position,
                    'match_score': recommendation.match_score
                })
            except JobPosting.DoesNotExist:
                continue
        
        return json.dumps({
            'status': 'success',
            'user_id': user_id,
            'saved_count': len(saved_recommendations),
            'recommendations': saved_recommendations
        }, ensure_ascii=False, default=str)

    # ===== Agents =====
    @agent
    def resume_inspector(self) -> Agent:
        return Agent(
            role="Resume Inspector",
            goal="이력서를 상세히 분석하여 지원자의 기술 스택, 경력, 강점을 파악합니다.",
            backstory="당신은 10년 경력의 HR 전문가이자 기술 채용 컨설턴트입니다. "
                      "지원자의 이력서를 면밀히 분석하여 핵심 역량과 경험을 추출하는 전문가입니다.",
            tools=[self.get_resume_tool, self.analyze_resume_tool],
            llm=LLM(
                model="gpt-4o",
                api_key=os.getenv("OPENAI_API_KEY"),
            ),
            verbose=True,
        )
        
    @agent
    def job_posting_inspector(self) -> Agent:
        return Agent(
            role="Job Posting Inspector",
            goal="채용 공고를 분석하여 요구 사항, 우대 사항, 회사 정보를 파악합니다.",
            backstory="당신은 채용 공고 분석 전문가입니다. "
                      "공고에서 핵심 요구사항, 우대사항, 회사 문화를 정확히 파악하여 구조화합니다.",
            tools=[self.fetch_job_postings_tool],
            llm=LLM(
                model="gemini-2.5-flash",
                api_key=os.getenv("GOOGLE_API_KEY"),
            ),
            verbose=True,
        )
        
    @agent
    def job_hunter(self) -> Agent:
        return Agent(
            role="Job Hunter",
            goal="이력서와 채용 공고를 매칭하여 가장 적합한 Top 10 공고를 추천합니다.",
            backstory="당신은 경력 컨설턴트로서 수천 건의 성공적인 매칭 경험을 가진 전문가입니다. "
                      "지원자의 강점과 공고의 요구사항을 비교 분석하여 최적의 매칭을 찾아냅니다.",
            tools=[self.save_recommendations_tool],
            llm=LLM(
                model="gemini-2.5-pro",
                api_key=os.getenv("GOOGLE_API_KEY"),
            ),
            verbose=True,
        )

    @task
    def fetch_job_postings_task(self) -> Task:
        return Task(
            description=f"""
            'Fetch Job Postings from Database' 도구를 사용하여 데이터베이스에서 모든 채용 공고를 조회합니다.
            
            단계:
            1. 'Fetch Job Postings from Database' 도구 호출
            2. 반환된 공고 목록을 분석하여 주요 정보 파악
            3. 다음 단계(이력서 분석)로 전달할 수 있도록 정리
            
            출력: 채용 공고 리스트 (JSON 형식)
            """,
            expected_output="채용 공고 목록을 포함한 JSON 배열. 각 공고는 posting_id, company_name, position, requirements, preferred_points 등을 포함",
            agent=self.job_posting_inspector(),
        )

    @task
    def analyze_resume_task(self) -> Task:
        return Task(
            description=f"""
            사용자의 이력서를 분석합니다. 이력서에 변경사항이 없으면 캐시된 분석 결과를 사용합니다.
            
            단계:
            1. 'Get Resume and Analysis' 도구를 사용하여 user_id={self.user_id}의 이력서 조회
            2. 반환된 status 확인:
               - 'cached': 이미 분석된 결과가 있음 → analysis_result 사용
               - 'needs_analysis': 재분석 필요 → 3단계 진행
               - 'error': 오류 처리
            
            3. 재분석이 필요한 경우 (status='needs_analysis'):
               a. content를 분석하여 다음 정보 추출:
                  - skills: 기술 스택 (언어, 프레임워크, 도구)
                  - experiences: 경력 정보 (연차, 프로젝트, 성과)
                  - strengths: 핵심 강점
                  - career_years: 총 경력 연수
                  - preferred_areas: 선호 업무 영역
               b. 'Analyze Resume' 도구를 사용하여 분석 결과 저장
            
            출력: 이력서 분석 결과 (JSON 형식)
            """,
            expected_output="이력서 분석 결과를 포함한 JSON 객체. skills, experiences, strengths, career_years, preferred_areas 등을 포함",
            agent=self.resume_inspector(),
        )

    @task
    def recommend_jobs_task(self) -> Task:
        return Task(
            description=f"""
            채용 공고와 이력서 분석 결과를 기반으로 Top 10 추천 공고를 선정합니다.
            
            단계:
            1. 이전 태스크의 결과 받기:
               - 채용 공고 목록 (fetch_job_postings_task 결과)
               - 이력서 분석 결과 (analyze_resume_task 결과)
            
            2. 각 공고에 대해 매칭 점수 계산:
               - 기술 스택 매칭도 (40%)
               - 경력 요구사항 적합도 (30%)
               - 우대사항 일치도 (30%)
             
            3. 매칭 점수 기준으로 정렬 후 Top 10 선정
            
            4. 각 추천에 대해 다음 정보 생성:
               - posting_id: 공고 ID
               - rank: 순위 (1-10)
               - match_score: 매칭 점수 (0-100)
               - match_reason: 구체적인 추천 이유
            
            5. 'Save Job Recommendations' 도구를 사용하여 user_id={self.user_id}에 대한 추천 결과 저장
            
            출력: Top 10 추천 공고 목록 (JSON 형식)
            """,
            expected_output="Top 10 추천 공고 목록을 포함한 JSON 배열. 각 항목은 rank, posting_id, company_name, position, match_score, match_reason을 포함",
            agent=self.job_hunter(),
        )

    @crew
    def job_hunter_crew(self) -> Crew:
        """Job Hunter Crew를 생성하여 순차적으로 task 실행"""
        return Crew(
            agents=[
                self.job_posting_inspector(),
                self.resume_inspector(),
                self.job_hunter(),
            ],
            tasks=[
                self.fetch_job_postings_task(),
                self.analyze_resume_task(),
                self.recommend_jobs_task(),
            ],
            verbose=True,
        )
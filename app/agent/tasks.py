import os
from crewai import Agent, Task, Crew, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.tools import tool
from django.utils import timezone
from agent.models import JobPosting, Resume, JobRecommendation
from typing import Annotated
import json

from django.db.models import Q
from functools import reduce
import operator

@CrewBase
class JobHunterCrew():
    agents: list[Agent] = []
    crews: list[Crew] = []
    tasks: list[Task] = []

    def __init__(self, user_id: int = 1):
        self.user_id = user_id
        self._validate_api_keys()
    
    def _validate_api_keys(self):
        google_key = os.getenv("GOOGLE_API_KEY")
        if not google_key:
            raise ValueError("GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다.")

    # ===== Tools (Function calling) =====
    
    @tool("Fetch Filtered Job Postings Tool")
    def fetch_filtered_job_postings_tool(
        career_years: Annotated[int, "필터링할 경력 연수 (예: 3)"],
        skills: Annotated[list[str], "필터링할 기술 스택 리스트 (예: ['Python', 'Django'])"]
    ) -> str:
        """
        이력서 분석 결과를 바탕으로 데이터베이스에서 채용 공고를 사전 필터링합니다.
        """
        print(f"[Tool Call] fetch_filtered_job_postings_tool 호출됨. 경력: {career_years}, 스킬: {skills}")
        
        query_set = JobPosting.objects.all()
        
        if career_years is not None:
            if career_years == 0:
                 query_set = query_set.filter(career_min=0)
            else:
                query_set = query_set.filter(
                    Q(career_min__lte=career_years) & 
                    (Q(career_max__gte=career_years) | Q(career_max=0))
                )

        if skills:
            skill_queries = [
                Q(requirements__icontains=skill) | Q(preferred_points__icontains=skill)
                for skill in skills
            ]
            if skill_queries:
                combined_skill_query = reduce(operator.or_, skill_queries)
                query_set = query_set.filter(combined_skill_query)
                
        filtered_postings = query_set.distinct().values(
            'posting_id', 'url', 'company_name', 'position',
            'main_tasks', 'requirements', 'preferred_points',
            'location', 'district', 'employment_type',
            'career_min', 'career_max'
        )[:100]

        print(f"[Tool Call] {len(filtered_postings)} 건의 공고가 필터링되었습니다.")
        return json.dumps(list(filtered_postings), ensure_ascii=False, default=str)

    @tool("Get resume tool")
    def get_resume_tool(user_id: Annotated[int, "조회할 사용자의 ID"]) -> str:
        """이력서를 조회합니다."""
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

    @tool("Analyze resume tool")
    def analyze_resume_tool(user_id: Annotated[int, "사용자 ID"], 
                           analysis_result: Annotated[dict, "분석 결과 JSON"]) -> str:
        """분석 결과를 저장합니다."""
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

    @tool("Save recommendations tool")
    def save_recommendations_tool(user_id: Annotated[int, "사용자 ID"], 
                                 recommendations: Annotated[list, "추천 목록"]) -> str:
        """추천 목록을 저장합니다."""
        saved_recommendations = []
        for rec in recommendations[:10]:
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
            goal="이력서를 상세히 분석하여 지원자의 기술 스택, 경력 연차, 강점을 **JSON 형식**으로 추출합니다.",
            backstory="당신은 10년 경력의 HR 전문가이자 기술 채용 컨설턴트입니다. "
                      "지원자의 이력서를 면밀히 분석하여 핵심 역량과 경험을 추출하는 전문가입니다.",
            tools=[self.get_resume_tool, self.analyze_resume_tool],
            llm=LLM(
                model="gemini/gemini-2.0-flash",
                api_key=os.getenv("GOOGLE_API_KEY")
            ),
            verbose=True,
        )
        
    @agent
    def job_posting_inspector(self) -> Agent:
        return Agent(
            role="Job Posting Inspector",
            goal="이력서 분석 결과를 바탕으로 필터링된 채용 공고 목록을 가져옵니다.",
            backstory="당신은 채용 공고 분석 전문가입니다. "
                      "공고에서 핵심 요구사항, 우대사항, 회사 문화를 정확히 파악하여 구조화합니다.",
            tools=[self.fetch_filtered_job_postings_tool], 
            llm=LLM(
                model="gemini/gemini-2.5-flash",
                api_key=os.getenv("GOOGLE_API_KEY")
            ),
            verbose=True,
        )
        
    @agent
    def job_hunter(self) -> Agent:
        return Agent(
            role="Job Hunter",
            goal="**필터링된 공고 목록**과 이력서를 매칭하여 가장 적합한 Top 10 공고를 추천합니다.",
            backstory="당신은 경력 컨설턴트로서 수천 건의 성공적인 매칭 경험을 가진 전문가입니다. "
                      "지원자의 강점과 공고의 요구사항을 비교 분석하여 최적의 매칭을 찾아냅니다.",
            tools=[self.save_recommendations_tool],
            llm=LLM(
                model="gemini/gemini-2.0-flash",
                api_key=os.getenv("GOOGLE_API_KEY")
            ),
            verbose=True,
        )

    # ===== Tasks =====

    @task
    def analyze_resume_task(self) -> Task:
        return Task(
            description=f"""
            [첫 번째 단계]
            사용자의 이력서를 분석하여 다음 단계를 위한 **구조화된 JSON 데이터**를 생성합니다.
            
            단계:
            1. 'Get resume tool' 도구를 사용하여 user_id={self.user_id}의 이력서 조회
            2. 반환된 status 확인:
               - 'cached': 이미 분석된 결과가 있음 → analysis_result 사용
               - 'needs_analysis': 재분석 필요 → 3단계 진행
            
            3. 재분석이 필요한 경우 (status='needs_analysis'):
               a. 'content'를 면밀히 분석하여 다음 정보 추출 (필수!):
                  - skills: 핵심 기술 스택 (리스트, 예: ["Python", "Django", "C++"])
                  - career_years: 총 경력 연수 (숫자, 예: 3). 신입은 0.
                  - experiences: 주요 경험 및 프로젝트
                  - strengths: 핵심 강점
               b. 'Analyze resume tool' 도구를 사용하여 이 JSON 분석 결과를 저장
            
            출력: 다음 태스크(공고 필터링)에서 사용할 이력서 분석 결과 (JSON 형식)
            """,
            expected_output="""
            필터링의 기준이 되는 이력서 분석 JSON 객체.
            
            예시:
            {{
              "status": "success",
              "user_id": 1,
              "analysis_result": {{
                "skills": ["Python", "Django", "FastAPI", "C++"],
                "career_years": 3,
                "strengths": "비동기 처리 및 대용량 트래픽 경험"
              }},
              "analyzed_at": "2025-10-27T15:30:00Z"
            }}
            """,
            agent=self.resume_inspector(),
        )

    @task
    def fetch_job_postings_task(self) -> Task:
        return Task(
            description=f"""
            [두 번째 단계]
            이전 단계(analyze_resume_task)의 이력서 분석 결과를 사용하여, 
            DB에서 관련 있는 채용 공고만 '사전 필터링'합니다.
            
            단계:
            1. context에서 이전 태스크(analyze_resume_task)의 출력을 받습니다.
            2. 출력 JSON에서 'analysis_result.career_years'와 'analysis_result.skills'를 추출합니다.
            3. 'Fetch Filtered Job Postings Tool' 도구를 호출하여 필터링된 공고 목록을 가져옵니다.
               - career_years 파라미터: 추출한 경력 연수
               - skills 파라미터: 추출한 스킬 리스트
            
            출력: 사전 필터링된 상위 100개의 채용 공고 리스트 (JSON 형식)
            """,
            expected_output="사전 필터링된 최대 100개의 채용 공고 목록을 포함한 JSON 배열.",
            agent=self.job_posting_inspector(),
            context=[self.analyze_resume_task()],
        )

    @task
    def recommend_jobs_task(self) -> Task:
        return Task(
            description=f"""
            [세 번째 단계]
            **필터링된 채용 공고 목록**과 **이력서 분석 결과**를 기반으로 
            최종 Top 10 추천 공고를 선정합니다.
            
            단계:
            1. context에서 이전 태스크들의 결과 받기:
               - 필터링된 채용 공고 목록 (fetch_job_postings_task 결과)
               - 이력서 분석 결과 (analyze_resume_task 결과)
            
            2. 이력서와 '필터링된 공고 목록(최대 100개)'을 정밀 비교하여 매칭 점수 계산:
               - 기술 스택 매칭도 (40%)
               - 경력 요구사항 적합도 (30%)
               - 우대사항 일치도 (30%)
            
            3. 매칭 점수 기준으로 정렬 후 Top 10 선정
            
            4. 각 추천에 대해 다음 정보 생성:
               - posting_id: 공고 ID
               - rank: 순위 (1-10)
               - match_score: 매칭 점수 (0-100)
               - match_reason: 구체적인 추천 이유 (한국어로 3줄 이내)
            
            5. 'Save recommendations tool' 도구를 사용하여 user_id={self.user_id}에 대한 추천 결과 저장
            
            출력: Top 10 추천 공고 목록 (JSON 형식)
            """,
            expected_output="""
            Top 10 추천 공고 목록을 포함한 JSON 배열. 
            각 항목은 rank, posting_id, company_name, position, match_score, match_reason을 포함.
            
            예시:
            {{
              "status": "success",
              "user_id": 1,
              "saved_count": 10,
              "recommendations": [
                {{
                  "rank": 1,
                  "posting_id": "12345",
                  "company_name": "테크컴퍼니",
                  "position": "백엔드 개발자",
                  "match_score": 95,
                  "match_reason": "Python/Django 스택 완벽 매칭, 3년 경력 요구사항 부합, MSA 경험 우대"
                }}
              ]
            }}
            """,
            agent=self.job_hunter(),
            context=[self.analyze_resume_task(), self.fetch_job_postings_task()],
        )

    @crew
    def job_hunter_crew(self) -> Crew:
        """Job Hunter Crew를 생성하여 순차적으로 task 실행"""
        
        return Crew(
            agents=[
                self.resume_inspector(),
                self.job_posting_inspector(),
                self.job_hunter(),
            ],
            tasks=[
                self.analyze_resume_task(),
                self.fetch_job_postings_task(),
                self.recommend_jobs_task(),
            ],
            verbose=True,
        )
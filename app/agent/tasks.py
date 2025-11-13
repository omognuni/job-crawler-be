from agent.agents import JobAgents
from agent.schemas import FinalRecommendationOutput
from crewai import Task

agents = JobAgents()


class JobTasks:
    def analyze_resume_task(self, user_id: int) -> Task:
        return Task(
            description=f"""
            [첫 번째 단계]
            사용자의 이력서를 분석하여 다음 단계를 위한 **구조화된 JSON 데이터**를 생성합니다.

            단계:
            1. 'Get resume tool' 도구를 사용하여 user_id={user_id}의 이력서 조회
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
            agent=agents.resume_inspector(),
        )

    def fetch_job_postings_task(self) -> Task:
        return Task(
            description="""
            [두 번째 단계]
            이전 단계(analyze_resume_task)의 이력서 분석 결과를 사용하여,
            DB에서 관련 있는 채용 공고만 '사전 필터링'합니다.

            단계:
            1. context에서 이전 태스크(analyze_resume_task)의 출력을 받습니다.
            2. 출력 JSON에서 'analysis_result.career_years'와 'analysis_result.skills'를 추출합니다.
            3. 'Fetch Filtered Job Postings Tool' 도구를 호출하여 필터링된 공고 목록을 가져옵니다.
                - career_years 파라미터: 추출한 경력 연수
                - skills 파라미터: 추출한 스킬 리스트

            **[ ❗ 매우 중요 - 에이전트 지시사항 ]**
            - 당신('Job Posting Inspector')의 유일한 임무는 'Fetch Filtered Job Postings Tool'을 **단 한 번** 호출하는 것입니다.
            - **절대로** 'Save recommendations tool' 또는 'Analyze resume tool' 등 다른 도구를 호출하지 마십시오.
            - 이 Task는 오직 공고를 '가져오는(Fetch)' 단계입니다. '저장(Save)'은 다음 에이전트의 역할입니다.

            출력: 사전 필터링된 상위 100개의 채용 공고 리스트 (JSON 형식). 툴이 반환한 결과를 그대로 출력해야 합니다.
            """,
            expected_output="사전 필터링된 최대 100개의 채용 공고 목록을 포함한 JSON 배열.",
            agent=agents.job_posting_inspector(),
            context=[self.analyze_resume_task(0)],  # user_id is not used here
        )

    def recommend_jobs_task(self, user_id: int) -> Task:
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

            5. 'Save recommendations tool' 도구를 사용하여 user_id={user_id}에 대한 추천 결과 저장

            6. **[ ❗ 매우 중요 ]** 'Save recommendations tool'이 반환한 JSON 문자열을 그대로 당신의 최종 답변(Final Answer)으로 사용하세요.
            어떤 인사말, 설명, 요약, 또는 "끝" 같은 추가 텍스트도 절대 포함하지 마세요. 오직 JSON 문자열만 반환해야 합니다.
            """,
            expected_output="""
            Top 10 추천 공고 목록을 포함한 JSON 배열.
            각 항목은 rank, url, company_name, position, match_score, match_reason을 포함.

            예시:
            {{
              "status": "success",
              "user_id": 1,
              "saved_count": 10,
              "recommendations": [
                {{
                  "rank": 1,
                  "url": "https://www.wanted.co.kr/wd/12345",
                  "company_name": "테크컴퍼니",
                  "position": "백엔드 개발자",
                  "match_score": 95,
                  "match_reason": "Python/Django 스택 완벽 매칭, 3년 경력 요구사항 부합, MSA 경험 우대"
                }}
              ]
            }}
            """,
            agent=agents.job_hunter(),
            context=[
                self.analyze_resume_task(user_id),
                self.fetch_job_postings_task(),
            ],
            output_json=FinalRecommendationOutput,
        )

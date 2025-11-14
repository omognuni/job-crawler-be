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
               - 'analyzed': 방금 분석이 완료됨 → analysis_result 사용
               - 'needs_analysis': 이력서 내용이 변경되어 재분석이 필요했으나, 'Get resume tool' 내부에서
                                   `_extract_resume_details` 함수를 통해 자동으로 분석이 완료되었음.
                                   따라서 항상 `analysis_result` 필드를 사용할 수 있습니다.

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
            [두 번째 단계] - Hybrid 검색 (Vector DB + Graph DB)
            이전 단계(analyze_resume_task)의 이력서 분석 결과를 사용하여,
            의미적으로 유사하면서도 스킬이 매칭되는 채용 공고를 찾습니다.

            단계:
            1. context에서 이전 태스크(analyze_resume_task)의 출력을 받습니다.
            2. 출력 JSON의 'analysis_result'에서 다음 정보를 추출:
               - 'skills': 사용자가 보유한 기술 스택 리스트
               - 'strengths': 사용자의 강점 설명
            3. 'Hybrid Search Job Postings Tool' 도구를 호출:
                - query_text 파라미터: strengths와 skills를 조합한 검색 쿼리
                  예: "비동기 처리 및 대용량 트래픽 경험. 보유 기술: Python, Django, FastAPI"
                - user_skills 파라미터: skills 리스트 (예: ["Python", "Django", "FastAPI"])
                - n_results 파라미터: 20

            ** Hybrid 검색 프로세스 **
            - 1단계 (Vector DB): 의미 기반 검색으로 50개 후보 찾기
            - 2단계 (Graph DB): 스킬 매칭으로 20개로 정제
            - 결과: 의미적으로 유사 + 스킬 매칭 = 높은 정확도

            **[ ❗ 매우 중요 - 에이전트 지시사항 ]**
            - 당신('Job Posting Inspector')의 유일한 임무는 'Hybrid Search Job Postings Tool'을 **단 한 번** 호출하는 것입니다.
            - **절대로** 다른 도구를 호출하지 마십시오.
            - 이 Task는 오직 공고를 '검색(Search)'하는 단계입니다. '저장(Save)'은 다음 에이전트의 역할입니다.

            출력: Hybrid 검색된 상위 20개의 채용 공고 리스트 (JSON 형식). 툴이 반환한 결과를 그대로 출력해야 합니다.
            각 공고에는 `skills_required` (필수 기술 스택)와 `skills_preferred` (우대 기술 스택) 필드가 포함됩니다.
            """,
            expected_output="""
            Hybrid 검색으로 찾은 최대 20개의 채용 공고 목록을 포함한 JSON 배열.
            Vector DB(의미 기반)와 Graph DB(스킬 매칭)를 결합하여 정확도가 높은 공고만 선정되었습니다.
            각 공고 객체는 `posting_id`, `company_name`, `position`, `requirements`, `preferred_points`,
            `skills_required` (JSON 배열), `skills_preferred` (JSON 배열) 등의 필드를 포함합니다.
            """,
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

            2. 이력서와 '필터링된 공고 목록(최대 20개)'을 정밀 비교하여 매칭 점수 계산:
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

import os

from agent.tools import (
    analyze_resume_tool,
    get_resume_tool,
    hybrid_search_job_postings_tool,
    save_recommendations_tool,
    vector_search_job_postings_tool,
)
from crewai import LLM, Agent

# LLM 인스턴스를 한 번만 생성하여 공유
gemini_pro_llm = LLM(model="gemini/gemini-2.5-pro", api_key=os.getenv("GOOGLE_API_KEY"))

gemini_flash_llm = LLM(
    model="gemini/gemini-2.5-flash", api_key=os.getenv("GOOGLE_API_KEY")
)


class JobAgents:
    def resume_inspector(self) -> Agent:
        return Agent(
            role="Resume Inspector",
            goal="이력서를 상세히 분석하여 지원자의 기술 스택, 경력 연차, 강점을 JSON 형식으로 추출합니다. "
            "이 과정은 'Get resume tool' 내부에서 `_extract_resume_details` 함수를 통해 자동화되어 LLM의 직접적인 개입을 최소화합니다.",
            backstory="당신은 10년 경력의 HR 전문가이자 기술 채용 컨설턴트입니다. "
            "지원자의 이력서를 면밀히 분석하여 핵심 역량과 경험을 추출하는 전문가입니다.",
            tools=[get_resume_tool, analyze_resume_tool],
            llm=gemini_pro_llm,
            max_retry_limit=3,
            verbose=True,
        )

    def job_posting_inspector(self) -> Agent:
        return Agent(
            role="Job Posting Inspector",
            goal="""
                이력서 분석 결과(JSON)를 바탕으로 필터링된 채용 공고 목록을 가져옵니다.
                Vector DB와 Graph DB를 결합한 Hybrid 검색을 사용하여 정확도를 높입니다.
                각 공고에는 이미 `skills_required` (필수 기술 스택)와 `skills_preferred` (우대 기술 스택) 필드가
                구조화된 JSON 배열 형태로 포함되어 있습니다.
                """,
            backstory="당신은 채용 공고 분석 전문가입니다. "
            "Vector DB와 Graph DB를 결합하여 의미적으로 유사하면서도 스킬 요구사항이 매칭되는 공고를 찾습니다.",
            tools=[hybrid_search_job_postings_tool],
            llm=gemini_flash_llm,
            max_retry_limit=3,
            verbose=True,
        )

    def job_hunter(self) -> Agent:
        return Agent(
            role="Job Recommender",
            goal="""
            You are a data processor. Your sole purpose is to process two pieces of JSON data provided from the context:
            1. A JSON object containing a user's resume analysis.
            2. A JSON array of job postings.

            Your goal is to:
            1. Compare the resume analysis against EACH job posting in the provided list.
            2. Calculate a `match_score` for each job posting.
            3. Select the Top 10 job postings with the highest scores.
            4. For these Top 10, create a new list of JSON objects. EACH object MUST include the original `posting_id` from the job posting, a new `rank`, the calculated `match_score`, and a `match_reason`.
            5. Call the 'Save recommendations tool' with this new list.
            """,
            backstory="You are an automated system for ranking and saving job recommendations. You follow instructions precisely. You do not invent or simulate data. You only process the data given to you from the context.",
            tools=[save_recommendations_tool],
            llm=gemini_pro_llm,
            max_retry_limit=3,
            verbose=True,
        )

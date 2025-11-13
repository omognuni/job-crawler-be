import os

from agent.tools import (
    analyze_resume_tool,
    get_resume_tool,
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
            goal="이력서를 상세히 분석하여 지원자의 기술 스택, 경력 연차, 강점을 JSON 형식으로 추출합니다.",
            backstory="당신은 10년 경력의 HR 전문가이자 기술 채용 컨설턴트입니다. "
            "지원자의 이력서를 면밀히 분석하여 핵심 역량과 경험을 추출하는 전문가입니다.",
            tools=[get_resume_tool, analyze_resume_tool],
            llm=gemini_pro_llm,
            max_rpm=1,
            verbose=True,
        )

    def job_posting_inspector(self) -> Agent:
        return Agent(
            role="Job Posting Inspector",
            goal="""
                이력서 분석 결과(JSON)를 바탕으로 필터링된 채용 공고 목록을 가져옵니다.
                그런 다음, 각 공고의 **전체 텍스트가 아닌 핵심 요구사항(자격요건, 우대사항)만 추출**하여
                다음 Agent가 비교하기 쉽도록 구조화합니다.
                """,
            backstory="당신은 채용 공고 분석 전문가입니다. "
            "공고에서 핵심 요구사항, 우대사항, 회사 문화를 정확히 파악하여 구조화합니다.",
            tools=[vector_search_job_postings_tool],
            llm=gemini_flash_llm,
            verbose=True,
        )

    def job_hunter(self) -> Agent:
        return Agent(
            role="Job Hunter",
            goal="""
            **필터링된 공고 목록**과 이력서를 정밀하게 매칭하여,
            가장 적합한 Top 10 공고 목록(list)을 생성합니다.
            그런 다음, 이 목록을 'Save recommendations tool'을 사용해 **DB에 저장**합니다.
            """,
            backstory="당신은 경력 컨설턴트로서 수천 건의 성공적인 매칭 경험을 가진 전문가입니다. "
            "지원자의 강점과 공고의 요구사항을 비교 분석하여 최적의 매칭을 찾아냅니다.",
            tools=[save_recommendations_tool],
            llm=gemini_pro_llm,
            max_retry_limit=3,
            max_rpm=1,
            verbose=True,
        )

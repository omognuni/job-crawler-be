import json
from typing import Annotated

from crewai.tools import tool
from django.utils import timezone
from job.models import JobPosting, JobRecommendation, Resume

# Phase 2.2: search 서비스 분리 완료
# - vector_search_job_postings_tool → search.services 사용
# - hybrid_search_job_postings_tool → search.services 사용


@tool("Vector Search Job Postings Tool")
def vector_search_job_postings_tool(
    query_text: Annotated[str, "유사도 검색을 위한 쿼리 텍스트 (이력서 요약 등)"],
    n_results: Annotated[int, "가져올 결과의 수"] = 20,
) -> str:
    """
    주어진 쿼리 텍스트와 의미적으로 유사한 채용 공고를 벡터 DB에서 검색합니다.

    Phase 2.2: search.services.SearchService 사용
    """
    from search.services import vector_search_job_postings

    return vector_search_job_postings(query_text, n_results)


@tool("Hybrid Search Job Postings Tool")
def hybrid_search_job_postings_tool(
    query_text: Annotated[str, "유사도 검색을 위한 쿼리 텍스트 (이력서 요약 등)"],
    user_skills: Annotated[list[str], "사용자가 보유한 기술 스택 리스트"],
    n_results: Annotated[int, "최종 반환할 결과의 수"] = 20,
) -> str:
    """
    Vector DB와 Graph DB를 결합한 2단계 검색으로 정확도를 높입니다.
    1단계: Vector DB에서 의미 기반 검색 (50개)
    2단계: Graph DB에서 스킬 기반 필터링 (n_results개)

    Phase 2.2: search.services.SearchService 사용
    """
    from search.services import hybrid_search_job_postings

    return hybrid_search_job_postings(query_text, user_skills, n_results)


@tool("Get resume tool")
def get_resume_tool(user_id: Annotated[int, "조회할 사용자의 ID"]) -> str:
    """이력서를 조회합니다."""
    try:
        resume = Resume.objects.get(user_id=user_id)
        if resume.needs_analysis():
            # TODO: agent 앱 deprecated - 실제 분석은 resume/tasks.py의 process_resume 사용
            # Celery 태스크 트리거
            from job.tasks import process_resume

            process_resume.delay(user_id)

            # 분석 중 상태 반환
            return json.dumps(
                {
                    "status": "analysis_scheduled",
                    "user_id": resume.user_id,
                    "message": "Resume analysis has been scheduled. Use the API to check status.",
                    "analyzed_at": str(resume.analyzed_at),
                },
                ensure_ascii=False,
                default=str,
            )
        else:
            return json.dumps(
                {
                    "status": "cached",
                    "user_id": resume.user_id,
                    "content": resume.content,
                    "analysis_result": resume.analysis_result,
                    "analyzed_at": str(resume.analyzed_at),
                },
                ensure_ascii=False,
                default=str,
            )
    except Resume.DoesNotExist:
        return json.dumps(
            {
                "status": "error",
                "message": f"User {user_id}의 이력서를 찾을 수 없습니다.",
            },
            ensure_ascii=False,
        )


@tool("Analyze resume tool")
def analyze_resume_tool(
    user_id: Annotated[int, "사용자 ID"],
    analysis_result: Annotated[dict, "분석 결과 JSON"],
) -> str:
    """분석 결과를 저장합니다."""
    try:
        resume = Resume.objects.get(user_id=user_id)
        resume.analysis_result = analysis_result
        resume.analyzed_at = timezone.now()
        resume.save()
        return json.dumps(
            {
                "status": "success",
                "user_id": user_id,
                "analysis_result": analysis_result,
                "analyzed_at": str(resume.analyzed_at),
            },
            ensure_ascii=False,
            default=str,
        )
    except Resume.DoesNotExist:
        return json.dumps(
            {
                "status": "error",
                "message": f"User {user_id}의 이력서를 찾을 수 없습니다.",
            },
            ensure_ascii=False,
        )


@tool("Save recommendations tool")
def save_recommendations_tool(
    user_id: Annotated[int, "사용자 ID"],
    recommendations: Annotated[list, "추천 목록"],
) -> str:
    """추천 목록을 저장합니다."""
    saved_recommendations = []
    for rec in recommendations[:10]:
        try:
            job_posting = None
            if "posting_id" in rec and rec["posting_id"]:
                job_posting = JobPosting.objects.get(posting_id=rec["posting_id"])
            elif "url" in rec and rec["url"]:
                job_posting = JobPosting.objects.get(url=rec["url"])
            else:
                continue

            recommendation = JobRecommendation.objects.create(
                user_id=user_id,
                job_posting=job_posting,
                rank=rec["rank"],
                match_score=rec["match_score"],
                match_reason=rec["match_reason"],
            )
            saved_recommendations.append(
                {
                    "id": recommendation.id,
                    "rank": recommendation.rank,
                    "url": job_posting.url,
                    "company_name": job_posting.company_name,
                    "position": job_posting.position,
                    "match_score": recommendation.match_score,
                    "match_reason": recommendation.match_reason,
                }
            )
        except JobPosting.DoesNotExist:
            continue
    return json.dumps(
        {
            "status": "success",
            "user_id": user_id,
            "saved_count": len(saved_recommendations),
            "recommendations": saved_recommendations,
        },
        ensure_ascii=False,
        default=str,
    )

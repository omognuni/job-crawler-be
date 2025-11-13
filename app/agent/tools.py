import json
import operator
from functools import reduce
from typing import Annotated

from common.vector_db import vector_db_client
from crewai.tools import tool
from django.db.models import Case, Q, When
from django.utils import timezone
from job.models import JobPosting, JobRecommendation, Resume


@tool("Vector Search Job Postings Tool")
def vector_search_job_postings_tool(
    query_text: Annotated[str, "유사도 검색을 위한 쿼리 텍스트 (이력서 요약 등)"],
    n_results: Annotated[int, "가져올 결과의 수"] = 100,
) -> str:
    """
    주어진 쿼리 텍스트와 의미적으로 유사한 채용 공고를 벡터 DB에서 검색합니다.
    """
    print(
        f"[Tool Call] vector_search_job_postings_tool 호출됨. Query: {query_text[:50]}..."
    )

    # 1. Vector DB에서 유사 공고 ID 검색
    collection = vector_db_client.get_or_create_collection("job_postings")
    query_result = vector_db_client.query(
        collection=collection,
        query_texts=[query_text],
        n_results=n_results,
    )

    posting_ids = query_result["ids"][0]
    if not posting_ids:
        return json.dumps([], ensure_ascii=False)

    # 2. ID를 사용하여 Postgres DB에서 전체 공고 정보 조회
    # ChromaDB는 ID를 문자열로 저장하므로 정수형으로 변환 필요
    int_posting_ids = [int(pid) for pid in posting_ids]

    # 순서를 보장하면서 조회
    preserved_order = Case(
        *[When(posting_id=pk, then=pos) for pos, pk in enumerate(int_posting_ids)]
    )
    query_set = JobPosting.objects.filter(posting_id__in=int_posting_ids).order_by(
        preserved_order
    )

    filtered_postings = list(
        query_set.values(
            "posting_id",
            "url",
            "company_name",
            "position",
            "main_tasks",
            "requirements",
            "preferred_points",
            "location",
            "district",
            "employment_type",
            "career_min",
            "career_max",
        )
    )

    print(f"[Tool Call] {len(filtered_postings)} 건의 공고가 벡터 검색되었습니다.")
    return json.dumps(filtered_postings, ensure_ascii=False, default=str)


@tool("Get resume tool")
def get_resume_tool(user_id: Annotated[int, "조회할 사용자의 ID"]) -> str:
    """이력서를 조회합니다."""
    try:
        resume = Resume.objects.get(user_id=user_id)
        if resume.needs_analysis():
            return json.dumps(
                {
                    "status": "needs_analysis",
                    "user_id": resume.user_id,
                    "content": resume.content,
                    "message": "이력서 분석이 필요합니다. analyze_resume_tool을 사용하세요.",
                },
                ensure_ascii=False,
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
            job_posting = JobPosting.objects.get(posting_id=rec["posting_id"])
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

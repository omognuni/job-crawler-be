import json
import operator
from functools import reduce
from typing import Annotated

from crewai.tools import tool
from django.db.models import Q
from django.utils import timezone
from job.models import JobPosting, JobRecommendation, Resume


@tool("Fetch Filtered Job Postings Tool")
def fetch_filtered_job_postings_tool(
    career_years: Annotated[int, "필터링할 경력 연수 (예: 3)"],
    skills: Annotated[
        list[str], "필터링할 기술 스택 리스트 (예: ['Python', 'Django'])"
    ],
) -> str:
    """
    이력서 분석 결과를 바탕으로 데이터베이스에서 채용 공고를 사전 필터링합니다.
    """
    print(
        f"[Tool Call] fetch_filtered_job_postings_tool 호출됨. 경력: {career_years}, 스킬: {skills}"
    )

    query_set = JobPosting.objects.all()

    if career_years is not None:
        if career_years == 0:
            query_set = query_set.filter(career_min=0)
        else:
            query_set = query_set.filter(
                Q(career_min__lte=career_years)
                & (Q(career_max__gte=career_years) | Q(career_max=0))
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
    )[:100]

    print(f"[Tool Call] {len(filtered_postings)} 건의 공고가 필터링되었습니다.")
    return json.dumps(list(filtered_postings), ensure_ascii=False, default=str)


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

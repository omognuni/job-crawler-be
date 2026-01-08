from __future__ import annotations

import logging
from typing import Optional

from common.application.result import Err, Ok, Result
from common.ports.graph_store import GraphStorePort
from common.ports.recommendation_evaluator import RecommendationEvaluatorPort
from common.ports.vector_store import VectorStorePort
from job.models import JobPosting
from recommendation.domain.scoring import (
    calculate_match_score_and_reason,
    calculate_position_similarity,
)
from recommendation.models import JobRecommendation, RecommendationPrompt
from resume.models import Resume

logger = logging.getLogger(__name__)


class GenerateRecommendationsUseCase:
    """
    추천 생성 유스케이스.

    현재는 기존 RecommendationService의 로직을 그대로 사용하되,
    Vector/Graph 접근은 Port로 주입받아 외부 시스템 결합을 줄입니다.
    """

    def __init__(
        self,
        *,
        vector_store: VectorStorePort,
        graph_store: GraphStorePort,
        evaluator: RecommendationEvaluatorPort,
    ):
        self._vector_store = vector_store
        self._graph_store = graph_store
        self._evaluator = evaluator

    def execute(
        self,
        *,
        resume_id: int,
        limit: int = 100,
        prompt_id: Optional[int] = None,
    ) -> Result[list[JobRecommendation]]:
        try:
            resume = Resume.objects.get(id=resume_id)
        except Resume.DoesNotExist:
            return Err(code="NOT_FOUND", message=f"Resume {resume_id} not found")

        user_id = resume.user_id
        analysis_result = resume.analysis_result or {}
        user_skills = set(analysis_result.get("skills", []))
        user_career_years = analysis_result.get("career_years", 0)
        user_position = (analysis_result.get("position") or "").strip()

        if not user_skills:
            return Ok([])

        # 1) Vector 후보
        candidate_posting_scores: dict[int, tuple[float, int]] = {}
        vector_scores: dict[int, float] = {}

        embedding = self._vector_store.get_embedding(
            collection_name="resumes",
            doc_id=str(resume_id),
        )

        if embedding is not None:
            where_filter = None
            if user_career_years > 0:
                where_filter = {
                    "$and": [
                        {"career_min": {"$lte": user_career_years}},
                        {"career_max": {"$gte": user_career_years}},
                    ]
                }

            query_results = self._vector_store.query_by_embedding(
                collection_name="job_postings",
                query_embedding=embedding,
                n_results=50,
                min_similarity=0.7,
                where=where_filter,
            )

            if where_filter and (
                not query_results
                or not query_results.get("ids")
                or not query_results["ids"][0]
            ):
                query_results = self._vector_store.query_by_embedding(
                    collection_name="job_postings",
                    query_embedding=embedding,
                    n_results=50,
                    min_similarity=0.7,
                    where=None,
                )

            if query_results and query_results.get("ids") and query_results["ids"][0]:
                vector_ids = query_results["ids"][0]
                distances = (
                    query_results.get("distances", [[]])[0]
                    if query_results.get("distances")
                    else []
                )
                for idx, pid in enumerate(vector_ids):
                    posting_id = int(pid)
                    if idx < len(distances):
                        similarity = 1 - (distances[idx] / 2.0)
                    else:
                        similarity = 0.5
                    vector_scores[posting_id] = similarity
                    candidate_posting_scores[posting_id] = (similarity, 0)
        else:
            # 텍스트 fallback
            query_text = (
                resume.experience_summary
                or f"보유 스킬: {', '.join(sorted(user_skills))}"
            )
            query_results = self._vector_store.query_by_text(
                collection_name="job_postings",
                query_text=query_text,
                n_results=50,
                min_similarity=0.7,
                where=None,
            )
            if query_results and query_results.get("ids") and query_results["ids"][0]:
                for pid in query_results["ids"][0]:
                    posting_id = int(pid)
                    candidate_posting_scores[posting_id] = (0.5, 0)

        # 2) Graph 후보
        graph_ids = self._graph_store.get_postings_by_skills(
            user_skills=user_skills, limit=50
        )
        for posting_id in graph_ids:
            if posting_id not in candidate_posting_scores:
                candidate_posting_scores[posting_id] = (0.5, 0)

        if not candidate_posting_scores:
            return Ok([])

        # 3) 스킬 매칭 수 + 재랭킹
        skill_match_scores: dict[int, int] = {}
        for pid in candidate_posting_scores.keys():
            skills_required = self._graph_store.get_required_skills(posting_id=pid)
            skill_match_scores[pid] = (
                len(user_skills & skills_required) if skills_required else 0
            )

        ranked_postings: list[tuple[int, float, int]] = []
        for posting_id, (vector_score, _) in candidate_posting_scores.items():
            skill_match_count = skill_match_scores.get(posting_id, 0)
            max_skills = max(len(user_skills), 10)
            skill_match_ratio = min(skill_match_count / max_skills, 1.0)

            if not user_position:
                hybrid_score = (vector_score * 0.6) + (skill_match_ratio * 0.4)
            else:
                try:
                    posting = JobPosting.objects.get(posting_id=posting_id)
                    posting_position = posting.position
                except JobPosting.DoesNotExist:
                    posting_position = ""
                position_similarity = calculate_position_similarity(
                    user_position=user_position,
                    job_position=posting_position,
                )

                w_pos = 0.5
                w_vec = 0.3
                w_skill = 0.2
                hybrid_score = (
                    (position_similarity * w_pos)
                    + (vector_score * w_vec)
                    + (skill_match_ratio * w_skill)
                )

            ranked_postings.append((posting_id, hybrid_score, skill_match_count))

        ranked_postings.sort(key=lambda x: x[1], reverse=True)
        matched_postings = [pid for pid, _, _ in ranked_postings[:limit]]
        if not matched_postings:
            return Ok([])

        # 4) match_score/match_reason
        recommendations: list[dict] = []
        if prompt_id:
            prompt = RecommendationPrompt.objects.get(id=prompt_id)
            postings_to_evaluate = []
            search_contexts = []
            for pid in matched_postings:
                try:
                    posting = JobPosting.objects.get(posting_id=pid)
                    postings_to_evaluate.append(posting)
                    search_contexts.append(
                        {
                            "hybrid_score": next(
                                (
                                    score
                                    for _pid, score, _ in ranked_postings
                                    if _pid == pid
                                ),
                                0.0,
                            ),
                            "vector_similarity": vector_scores.get(pid, 0.0),
                            "skill_matches": skill_match_scores.get(pid, 0),
                        }
                    )
                except JobPosting.DoesNotExist:
                    continue
            batch_results = self._evaluator.evaluate_batch(
                postings=postings_to_evaluate,
                resume=resume,
                prompt=prompt,
                search_contexts=search_contexts,
            )
            for posting, result in zip(postings_to_evaluate, batch_results):
                recommendations.append(
                    {
                        "posting_id": posting.posting_id,
                        "company_name": posting.company_name,
                        "position": posting.position,
                        "match_score": result["score"],
                        "match_reason": result["reason"],
                        "url": posting.url,
                        "location": posting.location,
                        "employment_type": posting.employment_type,
                    }
                )
        else:
            for pid in matched_postings:
                try:
                    posting = JobPosting.objects.get(posting_id=pid)
                except JobPosting.DoesNotExist:
                    continue
                score, reason = calculate_match_score_and_reason(
                    posting=posting,
                    user_skills=user_skills,
                    user_career_years=user_career_years,
                )
                recommendations.append(
                    {
                        "posting_id": pid,
                        "company_name": posting.company_name,
                        "position": posting.position,
                        "match_score": score,
                        "match_reason": reason,
                        "url": posting.url,
                        "location": posting.location,
                        "employment_type": posting.employment_type,
                    }
                )

        recommendations.sort(key=lambda x: x["match_score"], reverse=True)
        recommendation_obj_list: list[JobRecommendation] = []
        for idx, rec in enumerate(recommendations[:limit]):
            recommendation_obj_list.append(
                JobRecommendation(
                    user_id=user_id,
                    job_posting=JobPosting.objects.get(posting_id=rec["posting_id"]),
                    rank=idx + 1,
                    match_score=rec["match_score"],
                    match_reason=rec["match_reason"],
                )
            )

        return Ok(recommendation_obj_list[:limit])

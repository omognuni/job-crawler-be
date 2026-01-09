from __future__ import annotations

import logging
from typing import Optional

from common.application.result import Err, Ok, Result
from common.ports.graph_store import GraphStorePort
from common.ports.recommendation_evaluator import RecommendationEvaluatorPort
from common.ports.search_plan_builder import SearchPlanBuilderPort
from common.ports.vector_store import VectorStorePort
from job.models import JobPosting
from recommendation.domain.scoring import (
    map_position_to_category,
    normalize_position_text,
)
from recommendation.models import JobRecommendation, RecommendationPrompt
from resume.models import Resume
from skill.services import SkillExtractionService

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
        plan_builder: SearchPlanBuilderPort,
    ):
        self._vector_store = vector_store
        self._graph_store = graph_store
        self._evaluator = evaluator
        self._plan_builder = plan_builder

    def execute(
        self,
        *,
        resume_id: int,
        limit: int = 100,
        prompt_id: Optional[int] = None,
    ) -> Result[list[JobRecommendation]]:
        """
        추천 생성 흐름
        - 1) resume.analysis_result.position을 query로 벡터 검색해 후보(기본 50) 추림
        - 2) 후보를 (기술스택 > 자격요건 > 우대사항 > 벡터유사도) 우선순위로 점수화/정렬
        - 3) prompt_id가 있으면 LLM 평가 후 LLM score로 재정렬
        """
        try:
            resume = Resume.objects.get(id=resume_id)
        except Resume.DoesNotExist:
            return Err(code="NOT_FOUND", message=f"Resume {resume_id} not found")

        user_id = resume.user_id
        analysis_result = (
            resume.analysis_result if isinstance(resume.analysis_result, dict) else {}
        )
        user_skills = set(analysis_result.get("skills", []) or [])
        user_career_years = int(analysis_result.get("career_years", 0) or 0)
        user_position = str(analysis_result.get("position", "") or "").strip()

        if not user_skills:
            return Ok([])

        # 1) LLM Planner: 검색전략 생성 (API 키 없으면 fallback)
        plan = self._plan_builder.build_plan(resume=resume)
        plan_filters = (
            plan.get("filters") if isinstance(plan.get("filters"), dict) else {}
        )
        queries = plan.get("queries") if isinstance(plan.get("queries"), list) else []
        if not queries:
            return Ok([])

        def _parse_vector_query_results(qr: Optional[dict]) -> list[int]:
            if not qr or not qr.get("ids") or not qr["ids"][0]:
                return []
            ids = [int(x) for x in qr["ids"][0]]
            distances = qr.get("distances", [[]])[0] if qr.get("distances") else []
            for idx, pid in enumerate(ids):
                if idx < len(distances):
                    # Chroma distance(0~2 가정) -> similarity(0~1)
                    similarity = 1 - (distances[idx] / 2.0)
                else:
                    similarity = 0.0
                vector_scores[pid] = float(similarity)
            return ids

        # 2) Chunk-RAG Retrieval: job_posting_chunks에서 근거 스니펫 기반 후보를 모읍니다.
        chunks_collection = "job_posting_chunks"
        candidate_limit = 120  # LLM judge 전에는 조금 넉넉히 확보
        rerank_limit = 30  # rule-based로 줄인 뒤 LLM judge에 투입(최대 10은 evaluator 내부에서 자름)
        vector_scores: dict[int, float] = {}

        where_filter = None
        if user_career_years > 0:
            relaxed_career_min = user_career_years + 3
            where_filter = {
                "$and": [
                    {"career_min": {"$lte": relaxed_career_min}},
                    {"career_max": {"$gte": user_career_years}},
                ]
            }

        # 강한 포지션 필터
        # - 최종 랭킹 단계에서 확정적으로 제외합니다.
        # - chunk 컬렉션은 position_category 메타데이터가 없을 수 있어(where로 걸면 결과가 0이 됨),
        #   retrieval 단계에서는 where_filter에 position_category를 섞지 않습니다.
        user_position_category = map_position_to_category(
            normalize_position_text(user_position)
        )
        chunk_where_filter = where_filter

        # posting_id별 점수/근거 집계
        posting_scores: dict[int, float] = {}
        evidence_by_posting: dict[int, dict[str, list[tuple[float, str]]]] = {}

        def _add_evidence(
            *, posting_id: int, section: str, score: float, text: str
        ) -> None:
            sec = section or "unknown"
            evidence_by_posting.setdefault(posting_id, {}).setdefault(sec, []).append(
                (score, text)
            )

        for q in queries[:6]:
            if not isinstance(q, dict):
                continue
            query_text = str(q.get("text", "") or "").strip()
            if not query_text:
                continue
            try:
                weight = float(q.get("weight", 1.0))
            except Exception:
                weight = 1.0
            weight = min(max(weight, 0.0), 1.0)

            qr = self._vector_store.query_by_text(
                collection_name=chunks_collection,
                query_text=query_text,
                n_results=80,
                min_similarity=0.5,
                where=chunk_where_filter,
            )
            if not qr or not qr.get("ids") or not qr["ids"][0]:
                continue

            ids = qr.get("ids", [[]])[0] or []
            distances = qr.get("distances", [[]])[0] if qr.get("distances") else []
            docs = qr.get("documents", [[]])[0] if qr.get("documents") else []
            metas = qr.get("metadatas", [[]])[0] if qr.get("metadatas") else []

            for idx, _doc_id in enumerate(ids):
                distance = distances[idx] if idx < len(distances) else 2.0
                sim = max(0.0, 1.0 - (float(distance) / 2.0))
                score = sim * weight
                meta = metas[idx] if idx < len(metas) else {}
                if not isinstance(meta, dict):
                    continue
                pid = meta.get("posting_id")
                if pid is None:
                    continue
                try:
                    posting_id = int(pid)
                except Exception:
                    continue

                posting_scores[posting_id] = posting_scores.get(posting_id, 0.0) + score
                vector_scores[posting_id] = max(vector_scores.get(posting_id, 0.0), sim)

                section = str(meta.get("section", "") or "")
                text = str(docs[idx] if idx < len(docs) else "" or "").strip()
                if text:
                    _add_evidence(
                        posting_id=posting_id, section=section, score=score, text=text
                    )

        # chunk 인덱싱이 아직 안 되어 있거나(초기 배포), 테스트에서 vector store가 legacy path만 mock하는 경우가 있어
        # 결과가 비면 기존(job_postings) 벡터 검색으로 fallback 합니다.
        if not posting_scores:
            legacy_candidate_ids: list[int] = []
            embedding = self._vector_store.get_embedding(
                collection_name="resumes",
                doc_id=str(resume_id),
            )
            if embedding is not None:
                qr = self._vector_store.query_by_embedding(
                    collection_name="job_postings",
                    query_embedding=embedding,
                    n_results=50,
                    min_similarity=0.7,
                    where=where_filter,
                )
                legacy_candidate_ids = _parse_vector_query_results(qr)
                if where_filter and not legacy_candidate_ids:
                    qr = self._vector_store.query_by_embedding(
                        collection_name="job_postings",
                        query_embedding=embedding,
                        n_results=50,
                        min_similarity=0.7,
                        where=None,
                    )
                    legacy_candidate_ids = _parse_vector_query_results(qr)
            else:
                query_text = (
                    resume.experience_summary
                    or f"보유 스킬: {', '.join(sorted(user_skills))}"
                )
                qr = self._vector_store.query_by_text(
                    collection_name="job_postings",
                    query_text=query_text,
                    n_results=50,
                    min_similarity=0.7,
                    where=where_filter,
                )
                legacy_candidate_ids = _parse_vector_query_results(qr)
                if where_filter and not legacy_candidate_ids:
                    qr = self._vector_store.query_by_text(
                        collection_name="job_postings",
                        query_text=query_text,
                        n_results=50,
                        min_similarity=0.7,
                        where=None,
                    )
                    legacy_candidate_ids = _parse_vector_query_results(qr)

            if not legacy_candidate_ids:
                return Ok([])

            # legacy 후보에 대해 posting_scores를 최소 구성(근거는 DB 텍스트에서 간단 추출)
            for pid in legacy_candidate_ids:
                posting_scores[pid] = float(vector_scores.get(pid, 0.0))

        # 후보 보강(스킬 그래프) - 그래프도 where_filter와 같은 강한 필터를 적용하기 위해 DB에서 확인
        graph_ids = self._graph_store.get_postings_by_skills(
            user_skills=user_skills, limit=80
        )
        postings_for_graph = JobPosting.objects.filter(posting_id__in=graph_ids).only(
            "posting_id", "position"
        )
        for p in postings_for_graph:
            if user_position_category:
                job_cat = map_position_to_category(normalize_position_text(p.position))
                if not job_cat or job_cat != user_position_category:
                    continue
            if p.posting_id not in posting_scores:
                posting_scores[p.posting_id] = 0.0

        candidate_ids = sorted(
            posting_scores.keys(), key=lambda pid: posting_scores[pid], reverse=True
        )[:candidate_limit]
        postings_by_id = JobPosting.objects.in_bulk(
            candidate_ids, field_name="posting_id"
        )

        def _ratio(matched_count: int, total_count: int) -> float:
            if total_count <= 0:
                return 0.0
            return matched_count / total_count

        ranked_candidates: list[dict] = []
        for pid in candidate_ids:
            posting = postings_by_id.get(pid)
            if not posting:
                continue

            # 강한 포지션 필터(최종 안전장치):
            # - chunk where_filter로 걸렀더라도, legacy fallback/그래프 보강 경로에서 섞일 수 있어
            #   여기서 한번 더 확정적으로 제외합니다.
            if user_position_category:
                job_position_category = map_position_to_category(
                    normalize_position_text(posting.position)
                )
                if (
                    not job_position_category
                    or job_position_category != user_position_category
                ):
                    continue

            # 기술스택(최우선): JSON skills_required 기반
            stack_skills = set(posting.skills_required or [])
            stack_matched = user_skills & stack_skills
            stack_ratio = _ratio(len(stack_matched), len(stack_skills))

            # 자격요건(2순위): requirements 텍스트에서 스킬 추출
            req_text = posting.requirements or ""
            req_skills = set(SkillExtractionService.extract_skills(req_text))
            req_matched = user_skills & req_skills
            req_ratio = _ratio(len(req_matched), len(req_skills))

            # 우대사항(3순위): preferred_points 우선, 없으면 skills_preferred 사용
            pref_text = posting.preferred_points or posting.skills_preferred or ""
            pref_skills = set(SkillExtractionService.extract_skills(pref_text))
            pref_matched = user_skills & pref_skills
            pref_ratio = _ratio(len(pref_matched), len(pref_skills))

            vec_sim = float(vector_scores.get(pid, 0.0))

            # A안: 튜플 정렬(기술스택 > 자격요건 > 우대사항 > 벡터유사도)
            sort_key = (stack_ratio, req_ratio, pref_ratio, vec_sim)

            # 표기용 점수(0~100). 랭킹은 sort_key로 결정.
            display_score = min(
                100.0,
                max(
                    0.0,
                    100.0
                    * ((0.60 * stack_ratio) + (0.25 * req_ratio) + (0.15 * pref_ratio)),
                ),
            )

            parts: list[str] = []
            if stack_skills:
                parts.append(f"기술스택 {len(stack_matched)}/{len(stack_skills)}")
            else:
                parts.append("기술스택 정보 없음")
            if req_skills:
                parts.append(f"자격요건 {len(req_matched)}/{len(req_skills)}")
            else:
                parts.append("자격요건 스킬 추출 없음")
            if pref_skills:
                parts.append(f"우대사항 {len(pref_matched)}/{len(pref_skills)}")
            else:
                parts.append("우대사항 스킬 추출 없음")
            parts.append(f"포지션 벡터유사도 {vec_sim:.2f}")
            # S1: 근거 스니펫(섹션별 상위 일부) 포함
            ev = evidence_by_posting.get(pid, {})
            for sec in ("requirements", "preferred", "tasks", "stack", "position"):
                snippets = ev.get(sec, [])
                if not snippets:
                    continue
                snippets.sort(key=lambda x: x[0], reverse=True)
                top_texts = [t for _, t in snippets[:2] if t]
                if top_texts:
                    joined = " / ".join(top_texts)
                    parts.append(f"[근거:{sec}] {joined}")
            reason = " | ".join(parts)

            ranked_candidates.append(
                {
                    "posting": posting,
                    "posting_id": pid,
                    "sort_key": sort_key,
                    "display_score": display_score,
                    "vector_similarity": vec_sim,
                    "stack_match_ratio": stack_ratio,
                    "requirements_match_ratio": req_ratio,
                    "preferred_match_ratio": pref_ratio,
                    "stack_matches": len(stack_matched),
                    "requirements_matches": len(req_matched),
                    "preferred_matches": len(pref_matched),
                    "reason": reason,
                }
            )

        ranked_candidates.sort(key=lambda x: x["sort_key"], reverse=True)
        ranked_candidates = ranked_candidates[
            : min(rerank_limit, len(ranked_candidates))
        ]
        if not ranked_candidates:
            return Ok([])

        # 2) match_score/match_reason
        recommendations: list[dict] = []
        if prompt_id:
            prompt = RecommendationPrompt.objects.get(id=prompt_id)
            postings_to_evaluate = [x["posting"] for x in ranked_candidates]

            # evidence_quotes는 evaluator가 프롬프트에 포함할 수 있도록 "문장 리스트"로 전달
            def _collect_evidence_quotes(pid: int) -> list[str]:
                ev = evidence_by_posting.get(pid, {})
                quotes: list[str] = []
                for sec in ("requirements", "preferred", "tasks", "stack", "position"):
                    snippets = ev.get(sec, [])
                    if not snippets:
                        continue
                    snippets.sort(key=lambda x: x[0], reverse=True)
                    for _, t in snippets[:2]:
                        t = str(t or "").strip()
                        if t:
                            quotes.append(f"[{sec}] {t}")
                return quotes[:6]

            search_contexts = [
                {
                    # evaluator가 이미 사용하는 키들(호환 유지)
                    "vector_similarity": x["vector_similarity"],
                    "skill_matches": x["stack_matches"],
                    "hybrid_score": x["display_score"],  # 기존 key 재사용(표기용 점수)
                    # 신규 컨텍스트(프롬프트 품질 향상용)
                    "stack_match_ratio": x["stack_match_ratio"],
                    "requirements_match_ratio": x["requirements_match_ratio"],
                    "preferred_match_ratio": x["preferred_match_ratio"],
                    "stack_matches": x["stack_matches"],
                    "requirements_matches": x["requirements_matches"],
                    "preferred_matches": x["preferred_matches"],
                    "plan": plan,
                    "evidence_quotes": _collect_evidence_quotes(x["posting_id"]),
                }
                for x in ranked_candidates
            ]

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
                        "match_score": float(result.get("score", 0)),
                        "match_reason": str(result.get("reason", "") or ""),
                        "url": posting.url,
                        "location": posting.location,
                        "employment_type": posting.employment_type,
                    }
                )

            # 3) LLM score 재정렬(요청 사항)
            recommendations.sort(key=lambda x: x["match_score"], reverse=True)
        else:
            # 비-LLM 경로: 튜플 정렬 결과 그대로 사용
            for x in ranked_candidates:
                posting = x["posting"]
                recommendations.append(
                    {
                        "posting_id": posting.posting_id,
                        "company_name": posting.company_name,
                        "position": posting.position,
                        "match_score": x["display_score"],
                        "match_reason": x["reason"],
                        "url": posting.url,
                        "location": posting.location,
                        "employment_type": posting.employment_type,
                    }
                )

        recommendation_obj_list: list[JobRecommendation] = []
        postings_by_id_final = JobPosting.objects.in_bulk(
            [rec["posting_id"] for rec in recommendations],
            field_name="posting_id",
        )
        for idx, rec in enumerate(recommendations[:limit]):
            posting = postings_by_id_final.get(rec["posting_id"])
            if not posting:
                continue
            recommendation_obj_list.append(
                JobRecommendation(
                    user_id=user_id,
                    job_posting=posting,
                    rank=idx + 1,
                    match_score=rec["match_score"],
                    match_reason=rec["match_reason"],
                )
            )

        return Ok(recommendation_obj_list[:limit])

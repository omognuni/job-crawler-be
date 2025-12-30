"""
Recommendation Service

AI-Free 실시간 채용 공고 추천 엔진
벡터 유사도 + 스킬 그래프 매칭을 결합한 하이브리드 추천 시스템
"""

import logging
import time
from typing import Dict, List, Optional

from common.graph_db import graph_db_client
from common.vector_db import vector_db_client
from django.db import transaction
from job.models import JobPosting
from recommendation.models import JobRecommendation, RecommendationPrompt
from resume.models import Resume
from skill.services import SkillExtractionService

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    추천 서비스

    하이브리드 추천 엔진 (Vector + Graph)을 제공합니다.
    """

    @staticmethod
    def get_recommendations(
        resume_id: int, limit: int = 100, prompt_id: Optional[int] = None
    ) -> List[Dict]:
        """
        사용자에게 적합한 채용 공고 추천

        Args:
            resume_id: 이력서 ID
            limit: 반환할 추천 개수 (기본 100개)

        Returns:
            추천 공고 리스트 (각 항목은 posting_id, match_score, match_reason 포함)
        """
        try:
            # 1. Resume에서 스킬 및 경력 정보 추출
            resume = Resume.objects.get(id=resume_id)
            user_id = resume.user_id
            analysis_result = resume.analysis_result or {}
            user_skills = set(analysis_result.get("skills", []))
            user_career_years = analysis_result.get("career_years", 0)
            user_position = (analysis_result.get("position") or "").strip()

            if not user_skills:
                logger.warning(
                    f"Resume {resume_id} (User {user_id}) has no skills in analysis_result"
                )
                return []

            # 2. 하이브리드 검색 (Vector + Graph) 및 재랭킹
            candidate_posting_scores = (
                {}
            )  # posting_id -> (vector_score, skill_match_count)

            # [Vector Search] ChromaDB에서 유사한 공고 조회 (50개)
            resumes_collection = vector_db_client.get_or_create_collection("resumes")
            job_postings_collection = vector_db_client.get_or_create_collection(
                "job_postings"
            )

            # 이력서 임베딩 벡터를 직접 쿼리로 사용하여 공고 검색
            # 이 방식은 이력서 임베딩과 공고 임베딩을 직접 비교하므로 의미적 유사도 검색에 효과적
            # 대안: experience_summary 텍스트를 쿼리로 사용하는 방식도 가능하지만,
            #      임베딩-임베딩 직접 비교가 더 정확한 유사도 계산을 제공함
            resume_vector = resumes_collection.get(
                ids=[str(resume_id)], include=["embeddings"]
            )
            embeddings = resume_vector.get("embeddings") if resume_vector else None

            vector_scores = {}  # posting_id -> similarity_score
            # embeddings는 numpy array일 수 있어 truthiness(not embeddings)가 예외를 낼 수 있음
            embeddings_missing = embeddings is None
            if not embeddings_missing:
                try:
                    embeddings_missing = len(embeddings) == 0
                except Exception:
                    # 길이 확인이 불가능한 타입이면 "있다"로 취급
                    embeddings_missing = False

            if embeddings_missing:
                # 이력서 임베딩이 없으면 즉시 생성 시도 (Admin 재임베딩을 안 했거나 실패한 경우 대비)
                try:
                    from resume.embeddings import ResumeEmbeddingService

                    ResumeEmbeddingService.embed_resume(resume)
                    resume_vector = resumes_collection.get(
                        ids=[str(resume_id)], include=["embeddings"]
                    )
                    embeddings = (
                        resume_vector.get("embeddings") if resume_vector else None
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to ensure resume embedding for resume {resume_id}: {e}",
                        exc_info=True,
                    )

            # embeddings truthiness를 쓰지 않고 안전하게 길이로 판단
            embeddings_ready = embeddings is not None
            if embeddings_ready:
                try:
                    embeddings_ready = len(embeddings) > 0
                except Exception:
                    embeddings_ready = True

            if embeddings_ready:
                # 메타데이터 필터 구성 (경력 범위)
                where_filter = None
                if user_career_years > 0:
                    # 경력이 사용자의 경력 연차 범위에 맞는 공고만 필터링
                    # career_min <= user_career_years <= career_max
                    # ChromaDB where 필터는 $gte, $lte 등을 지원
                    where_filter = {
                        "$and": [
                            {"career_min": {"$lte": user_career_years}},
                            {"career_max": {"$gte": user_career_years}},
                        ]
                    }

                # 이력서 임베딩 벡터를 쿼리로 사용하여 유사한 공고 검색
                # 유사도 임계값 적용 (0.7 = 70% 유사도 이상)
                query_results = vector_db_client.query_by_embedding(
                    collection=job_postings_collection,
                    query_embeddings=embeddings,
                    n_results=50,
                    min_similarity=0.7,  # 최소 70% 유사도
                    where=where_filter,  # 메타데이터 필터
                )
                # 경력 필터가 너무 빡세서 결과가 없을 경우 필터 없이 재시도
                if where_filter and (
                    not query_results
                    or not query_results.get("ids")
                    or not query_results["ids"][0]
                ):
                    query_results = vector_db_client.query_by_embedding(
                        collection=job_postings_collection,
                        query_embeddings=embeddings,
                        n_results=50,
                        min_similarity=0.7,
                        where=None,
                    )

                if query_results and query_results.get("ids"):
                    vector_ids = query_results["ids"][0]
                    distances = (
                        query_results.get("distances", [[]])[0]
                        if query_results.get("distances")
                        else []
                    )

                    # distance를 similarity로 변환 (distance: 0=유사, 2=다름)
                    # similarity = 1 - (distance / 2)
                    for idx, pid in enumerate(vector_ids):
                        posting_id = int(pid)
                        if idx < len(distances):
                            distance = distances[idx]
                            similarity = 1 - (distance / 2.0)  # 0-1 범위로 변환
                        else:
                            # distances가 없는 경우에도 후보를 버리지 않도록 기본값 부여
                            similarity = 0.5
                        vector_scores[posting_id] = similarity
                        candidate_posting_scores[posting_id] = (similarity, 0)

                    logger.info(
                        f"Vector search found {len(vector_ids)} candidates (similarity >= 0.7)"
                    )
            else:
                # 임베딩이 끝내 없으면 experience_summary/skills 기반 텍스트 검색으로 fallback
                try:
                    query_text = (
                        resume.experience_summary
                        or f"보유 스킬: {', '.join(sorted(user_skills))}"
                    )
                    query_results = vector_db_client.query(
                        collection=job_postings_collection,
                        query_texts=[query_text],
                        n_results=50,
                        min_similarity=0.7,
                        where=None,
                    )
                    if (
                        query_results
                        and query_results.get("ids")
                        and query_results["ids"][0]
                    ):
                        for pid in query_results["ids"][0]:
                            posting_id = int(pid)
                            candidate_posting_scores[posting_id] = (0.5, 0)
                        logger.info(
                            f"Vector text fallback found {len(query_results['ids'][0])} candidates"
                        )
                except Exception as e:
                    logger.warning(
                        f"Vector text fallback failed for resume {resume_id}: {e}",
                        exc_info=True,
                    )

            # [Graph Search] Neo4j에서 스킬 기반 공고 조회 (50개)
            # 사용자의 스킬을 요구하는 공고를 직접 조회하여 Vector 검색의 누락을 보완
            graph_ids = RecommendationService._get_postings_by_skills(
                user_skills, limit=50
            )
            logger.info(f"Graph search found {len(graph_ids)} candidates")

            # Graph 검색 결과도 candidate에 추가 (벡터 점수 없으면 0.5 기본값)
            for posting_id in graph_ids:
                if posting_id not in candidate_posting_scores:
                    candidate_posting_scores[posting_id] = (0.5, 0)  # 기본 벡터 점수

            if not candidate_posting_scores:
                logger.info(f"No candidates found for user {user_id}")
                return []

            # 3. 스킬 매칭 점수 계산 및 재랭킹
            # 각 후보에 대해 스킬 매칭 수를 계산하고, 벡터 점수와 결합
            skill_match_scores = RecommendationService._calculate_skill_match_scores(
                list(candidate_posting_scores.keys()), user_skills
            )

            # 벡터 점수/스킬 매칭/포지션 유사도를 결합하여 재랭킹
            # - user_position이 비어있으면(분석 미완료 등) 기존 점수식을 유지하여 호환성을 보장
            # - user_position이 있으면 position 유사도를 가장 큰 가중치로 반영
            ranked_postings = []
            for posting_id, (vector_score, _) in candidate_posting_scores.items():
                skill_match_count = skill_match_scores.get(posting_id, 0)
                # 스킬 매칭 비율 계산 (임의로 최대 스킬 수를 10개로 가정)
                # 실제로는 공고의 전체 스킬 수를 사용하는 것이 좋지만, 여기서는 단순화
                max_skills = max(len(user_skills), 10)
                skill_match_ratio = min(skill_match_count / max_skills, 1.0)

                # 하이브리드 점수 계산
                if not user_position:
                    hybrid_score = (vector_score * 0.6) + (skill_match_ratio * 0.4)
                else:
                    try:
                        posting = JobPosting.objects.get(posting_id=posting_id)
                        posting_position = posting.position
                    except JobPosting.DoesNotExist:
                        posting_position = ""

                    position_similarity = (
                        RecommendationService._calculate_position_similarity(
                            user_position=user_position,
                            job_position=posting_position,
                        )
                    )

                    # position 유사도가 가장 높은 점수로 영향(가중치 최대)
                    w_pos = 0.5
                    w_vec = 0.3
                    w_skill = 0.2
                    hybrid_score = (
                        (position_similarity * w_pos)
                        + (vector_score * w_vec)
                        + (skill_match_ratio * w_skill)
                    )

                ranked_postings.append((posting_id, hybrid_score, skill_match_count))

            # 하이브리드 점수 기준 내림차순 정렬
            ranked_postings.sort(key=lambda x: x[1], reverse=True)

            # 상위 limit개 선택
            matched_postings = [pid for pid, _, _ in ranked_postings[:limit]]

            if not matched_postings:
                logger.info(f"No skill-matched postings for user {user_id}")
                return []

            # 4. 각 공고에 대해 match_score 계산 및 match_reason 생성
            recommendations = []

            # 재랭킹 결과에서 점수 정보 추출 (RAG 컨텍스트용)
            posting_hybrid_scores = {
                pid: score for pid, score, _ in ranked_postings[:limit]
            }
            posting_skill_counts = {
                pid: count for pid, _, count in ranked_postings[:limit]
            }

            # LLM 평가가 필요한 공고 수집
            postings_to_evaluate = []
            search_contexts = []  # 각 공고의 검색 컨텍스트
            if prompt_id:
                for posting_id in matched_postings:
                    try:
                        posting = JobPosting.objects.get(posting_id=posting_id)
                        postings_to_evaluate.append(posting)
                        # 검색 컨텍스트 정보 수집
                        hybrid_score = posting_hybrid_scores.get(posting_id, 0.0)
                        skill_count = posting_skill_counts.get(posting_id, 0)
                        vector_score = vector_scores.get(posting_id, 0.0)
                        search_contexts.append(
                            {
                                "hybrid_score": hybrid_score,
                                "vector_similarity": vector_score,
                                "skill_matches": skill_count,
                            }
                        )
                    except JobPosting.DoesNotExist:
                        continue

                # 일괄 평가 수행 (RAG 패턴: 검색 컨텍스트 포함)
                if postings_to_evaluate:
                    prompt = RecommendationPrompt.objects.get(id=prompt_id)
                    batch_results = (
                        RecommendationService._evaluate_match_batch_with_llm(
                            postings_to_evaluate, resume, prompt, search_contexts
                        )
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
                # 기존 로직 (Rule-based) - 개별 처리
                for posting_id in matched_postings:
                    try:
                        posting = JobPosting.objects.get(posting_id=posting_id)
                        score, reason = (
                            RecommendationService._calculate_match_score_and_reason(
                                posting, user_skills, user_career_years
                            )
                        )
                        recommendations.append(
                            {
                                "posting_id": posting_id,
                                "company_name": posting.company_name,
                                "position": posting.position,
                                "match_score": score,
                                "match_reason": reason,
                                "url": posting.url,
                                "location": posting.location,
                                "employment_type": posting.employment_type,
                            }
                        )
                    except JobPosting.DoesNotExist:
                        logger.warning(f"JobPosting {posting_id} not found")
                        continue

            # 5. match_score 기준 정렬 및 상위 limit개 반환
            recommendation_obj_list = []
            recommendations.sort(key=lambda x: x["match_score"], reverse=True)
            for idx, recommendation in enumerate(recommendations[:limit]):
                recommendation_obj_list.append(
                    JobRecommendation(
                        user_id=user_id,
                        job_posting=JobPosting.objects.get(
                            posting_id=recommendation["posting_id"]
                        ),
                        rank=idx + 1,
                        match_score=recommendation["match_score"],
                        match_reason=recommendation["match_reason"],
                    )
                )
            # 이미 받은 추천 공고가 있다면 공고 삭제 후 다시 저장
            with transaction.atomic():
                JobRecommendation.objects.filter(user_id=user_id).delete()
                JobRecommendation.objects.bulk_create(recommendation_obj_list)

            return recommendation_obj_list[:limit]

        except Resume.DoesNotExist:
            logger.error(f"Resume {resume_id} not found")
            return []
        except Exception as e:
            logger.error(
                f"Error generating recommendations for resume {resume_id}: {e}",
                exc_info=True,
            )
            return []

    @staticmethod
    def _normalize_position_text(text: str) -> str:
        """
        포지션 문자열 정규화 (간단/설명 가능한 규칙 기반)
        """
        if not text:
            return ""
        s = str(text).strip().lower()
        # 공백/구분자 제거로 포함 매칭 정확도 개선
        s = s.replace(" ", "")
        s = s.replace("/", "")
        s = s.replace("-", "")
        s = s.replace("_", "")
        return s

    @staticmethod
    def _map_position_to_category(normalized_text: str) -> str:
        """
        정규화된 포지션 문자열을 큰 카테고리로 매핑합니다.
        """
        if not normalized_text:
            return ""

        backend_keywords = ("backend", "백엔드", "server", "서버")
        frontend_keywords = ("frontend", "프론트", "web", "웹")
        devops_keywords = ("devops", "infra", "인프라", "sre", "platform", "플랫폼")
        data_ml_keywords = (
            "data",
            "ml",
            "ai",
            "머신러닝",
            "데이터",
            "research",
            "리서치",
        )
        mobile_keywords = ("android", "ios", "mobile", "모바일")

        if any(k in normalized_text for k in backend_keywords):
            return "backend"
        if any(k in normalized_text for k in frontend_keywords):
            return "frontend"
        if any(k in normalized_text for k in devops_keywords):
            return "devops"
        if any(k in normalized_text for k in data_ml_keywords):
            return "data_ml"
        if any(k in normalized_text for k in mobile_keywords):
            return "mobile"

        return ""

    @staticmethod
    def _calculate_position_similarity(user_position: str, job_position: str) -> float:
        """
        이력서 포지션과 공고 포지션의 유사도를 0~1로 반환합니다.
        - 카테고리 매핑이 되면 그것을 우선(설명 가능성/안정성)
        - 매핑 실패 시 간단한 문자열 동일/포함 규칙으로 보정
        """
        if not user_position or not job_position:
            return 0.0

        u = RecommendationService._normalize_position_text(user_position)
        j = RecommendationService._normalize_position_text(job_position)
        if not u or not j:
            return 0.0

        u_cat = RecommendationService._map_position_to_category(u)
        j_cat = RecommendationService._map_position_to_category(j)
        if u_cat and j_cat:
            return 1.0 if u_cat == j_cat else 0.0

        if u == j:
            return 1.0
        if u in j or j in u:
            return 0.8

        return 0.0

    @staticmethod
    def _calculate_skill_match_scores(
        posting_ids: List[int], user_skills: set
    ) -> Dict[int, int]:
        """
        각 공고에 대한 스킬 매칭 점수 계산

        Args:
            posting_ids: 후보 공고 ID 리스트
            user_skills: 사용자 스킬 집합

        Returns:
            posting_id -> 스킬 매칭 수 딕셔너리
        """
        if not user_skills:
            return {pid: 0 for pid in posting_ids}

        skill_scores = {}

        for posting_id in posting_ids:
            try:
                # Neo4j에서 공고의 필수 스킬 조회
                query = """
                MATCH (jp:JobPosting {posting_id: $posting_id})-[:REQUIRES_SKILL]->(skill:Skill)
                RETURN skill.name AS skill_name
                """

                result = graph_db_client.execute_query(
                    query, {"posting_id": posting_id}
                )

                if result:
                    posting_skills = {record["skill_name"] for record in result}
                    match_count = len(user_skills & posting_skills)
                    skill_scores[posting_id] = match_count
                else:
                    skill_scores[posting_id] = 0
            except Exception as e:
                logger.warning(
                    f"Error querying skills for posting {posting_id}: {e}",
                    exc_info=True,
                )
                skill_scores[posting_id] = 0
                continue

        return skill_scores

    @staticmethod
    def _filter_by_skill_graph(posting_ids: List[int], user_skills: set) -> List[int]:
        """
        Neo4j 그래프를 사용하여 스킬 매칭되는 공고 필터링

        Args:
            posting_ids: 후보 공고 ID 리스트
            user_skills: 사용자 스킬 집합

        Returns:
            스킬 매칭되는 공고 ID 리스트 (스킬 매칭 수 기준 내림차순 정렬)
        """
        if not user_skills:
            return posting_ids

        matched_postings = []

        for posting_id in posting_ids:
            try:
                # Neo4j에서 공고의 필수/우대 스킬 조회
                query = """
                MATCH (jp:JobPosting {posting_id: $posting_id})-[:REQUIRES_SKILL]->(skill:Skill)
                RETURN skill.name AS skill_name, 'required' AS skill_type
                """

                result = graph_db_client.execute_query(
                    query, {"posting_id": posting_id}
                )

                if result:
                    posting_skills = {record["skill_name"] for record in result}
                    # 스킬 매칭이 있는 경우만 포함
                    if user_skills & posting_skills:
                        match_count = len(user_skills & posting_skills)
                        matched_postings.append((posting_id, match_count))
            except Exception as e:
                logger.warning(
                    f"Error querying skills for posting {posting_id}: {e}",
                    exc_info=True,
                )
                continue

        # 스킬 매칭 수 기준 내림차순 정렬
        matched_postings.sort(key=lambda x: x[1], reverse=True)
        return [posting_id for posting_id, _ in matched_postings]

    @staticmethod
    def _get_postings_by_skills(user_skills: set, limit: int = 50) -> List[int]:
        """
        사용자 스킬을 포함하는 공고 조회 (Graph DB)

        Args:
            user_skills: 사용자 스킬 집합
            limit: 조회할 공고 수

        Returns:
            공고 ID 리스트
        """
        if not user_skills:
            return []

        try:
            # 사용자의 스킬 중 하나라도 요구하는 공고 조회 (최신순)
            query = """
            MATCH (jp:JobPosting)-[:REQUIRES_SKILL]->(skill:Skill)
            WHERE skill.name IN $user_skills
            RETURN jp.posting_id AS posting_id, count(skill) as match_count
            ORDER BY match_count DESC, jp.posting_id DESC
            LIMIT $limit
            """

            result = graph_db_client.execute_query(
                query, {"user_skills": list(user_skills), "limit": limit}
            )

            return [record["posting_id"] for record in result]

        except Exception as e:
            logger.warning(f"Error querying postings by skills: {e}", exc_info=True)
            return []

    @staticmethod
    def _calculate_match_score_and_reason(
        posting: JobPosting, user_skills: set, user_career_years: int
    ) -> tuple[int, str]:
        """
        공고와 사용자 간의 매칭 점수 및 매칭 사유 계산

        Args:
            posting: 채용 공고 객체
            user_skills: 사용자 스킬 집합
            user_career_years: 사용자 경력 연차

        Returns:
            (match_score, match_reason) 튜플
            - match_score: 0-100 점수
            - match_reason: 매칭 사유 텍스트
        """
        score = 0
        reasons = []

        # 1. 필수 스킬 매칭 (최대 50점)
        required_skills = set(posting.skills_required or [])
        if required_skills:
            matched_required = user_skills & required_skills
            required_match_ratio = len(matched_required) / len(required_skills)
            required_score = int(required_match_ratio * 50)
            score += required_score

            if required_match_ratio >= 0.7:
                reasons.append(
                    f"필수 스킬 {len(matched_required)}/{len(required_skills)}개 보유"
                )
            elif required_match_ratio >= 0.4:
                reasons.append(f"필수 스킬 일부 보유 ({len(matched_required)}개)")

        # 2. 우대사항 매칭 (최대 30점)
        if posting.skills_preferred:
            preferred_skills = set(
                SkillExtractionService.extract_skills(posting.skills_preferred)
            )
            if preferred_skills:
                matched_preferred = user_skills & preferred_skills
                preferred_match_ratio = len(matched_preferred) / len(preferred_skills)
                preferred_score = int(preferred_match_ratio * 30)
                score += preferred_score

                if matched_preferred:
                    reasons.append(f"우대사항 {len(matched_preferred)}개 충족")

        # 3. 경력 범위 일치 (최대 20점)
        career_min = posting.career_min
        career_max = posting.career_max

        if career_min <= user_career_years <= career_max:
            score += 20
            reasons.append(f"경력 요건 충족 ({user_career_years}년)")
        elif career_min <= user_career_years <= career_max + 2:
            # 상한보다 약간 많은 경우도 부분 점수
            score += 10
            reasons.append(f"경력 범위 근접 ({user_career_years}년)")

        # 4. 매칭 사유 텍스트 생성
        if reasons:
            match_reason = " | ".join(reasons)
        else:
            match_reason = "벡터 유사도 기반 매칭"

        # 점수는 최대 100점으로 제한
        score = min(score, 100)

        return score, match_reason

    @staticmethod
    def _evaluate_match_batch_with_llm(
        postings: List[JobPosting],
        resume: Resume,
        prompt: RecommendationPrompt,
        search_contexts: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """
        LLM을 사용하여 여러 공고와 이력서 간의 매칭 평가 (일괄 처리)
        RAG 패턴: 검색 컨텍스트(유사도 점수, 스킬 매칭 정보)를 포함

        Args:
            postings: 채용 공고 객체 리스트
            resume: 이력서 객체
            prompt: 사용할 프롬프트 객체
            search_contexts: 검색 컨텍스트 리스트 (각 공고의 유사도 점수, 스킬 매칭 수 등)

        Returns:
            평가 결과 리스트 [{"score": int, "reason": str}, ...]
        """
        import json
        import os
        import re

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("Google API key not found - using fallback")
            return [{"score": 50, "reason": "API 키 미설정"} for _ in postings]

        try:
            from google import genai
            from google.genai.errors import ClientError
            from google.genai.types import GenerateContentConfig

            client = genai.Client(api_key=api_key)

            # 이력서 요약
            resume_summary = resume.experience_summary or "이력서 내용 없음"
            skills = ", ".join(resume.analysis_result.get("skills", []))

            # 공고 목록 요약 (RAG: 검색 컨텍스트 포함)
            # 배치 크기 제한으로 토큰 수 제어 (10개씩 처리)
            max_batch_size = 10
            if len(postings) > max_batch_size:
                logger.warning(
                    f"Too many postings ({len(postings)}), limiting to {max_batch_size} for LLM evaluation"
                )
                postings = postings[:max_batch_size]
                if search_contexts:
                    search_contexts = search_contexts[:max_batch_size]

            jobs_text = ""
            for idx, posting in enumerate(postings):
                context_info = ""
                if search_contexts and idx < len(search_contexts):
                    ctx = search_contexts[idx]
                    context_info = f"""
                [Search Context - 이 공고는 다음 검색 기준으로 선별되었습니다]
                - 벡터 유사도 점수: {ctx.get('vector_similarity', 0):.2f}
                - 스킬 매칭 수: {ctx.get('skill_matches', 0)}개
                - 하이브리드 점수: {ctx.get('hybrid_score', 0):.2f}
                """

                jobs_text += f"""
                [Job {idx+1}]
                ID: {posting.posting_id}
                Company: {posting.company_name}
                Position: {posting.position}
                Main Tasks: {posting.main_tasks}
                Requirements: {posting.requirements}
                Preferred: {posting.preferred_points}{context_info}
                -------------------
                """

            # 프롬프트 구성 (RAG 패턴: 검색 컨텍스트 포함)
            full_prompt = f"""
            {prompt.content}

            [Candidate Resume Summary]
            {resume_summary}
            Skills: {skills}

            [Job Postings - 벡터 유사도 검색 및 스킬 그래프 매칭을 통해 선별된 후보들]
            {jobs_text}

            Based on the resume, evaluate the candidate's fit for EACH job posting above.
            Return a JSON list of objects, one for each job, in the same order.

            Each object must have:
            - score: Integer between 0 and 100
            - reason: A concise explanation (1 sentence, Korean)

            JSON Format Only:
            [
                {{
                    "score": 85,
                    "reason": "..."
                }},
                {{
                    "score": 40,
                    "reason": "..."
                }}
            ]
            """

            # LLM 호출 및 JSON 파싱 (재시도 로직 포함)
            max_retries = 3
            results = None

            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=full_prompt,
                        config=GenerateContentConfig(
                            temperature=0.2,
                            max_output_tokens=2000,  # 토큰 수 증가
                        ),
                    )

                    # JSON 파싱
                    result_text = response.text.strip()
                    result_text = re.sub(
                        r"^```json\s*|\s*```$", "", result_text, flags=re.MULTILINE
                    )
                    results = json.loads(result_text)

                    # 결과 개수 검증 및 보정
                    if len(results) != len(postings):
                        logger.warning(
                            f"Mismatch in batch results: expected {len(postings)}, got {len(results)}"
                        )
                        # 부족한 경우 기본값 채움
                        while len(results) < len(postings):
                            results.append({"score": 50, "reason": "분석 결과 누락"})
                        # 넘치는 경우 자름
                        results = results[: len(postings)]

                    break  # 파싱 성공 시 루프 종료

                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"JSON 파싱 실패 (시도 {attempt + 1}/{max_retries}): {e}. 재시도합니다."
                        )
                        continue
                    else:
                        logger.error(f"JSON 파싱 최종 실패: {e}")
                        # 최종 실패 시 기본값 반환
                        results = [
                            {"score": 50, "reason": "LLM 응답 파싱 실패"}
                            for _ in postings
                        ]
                        break

                except ClientError as e:
                    if e.code == 429:
                        if attempt < max_retries - 1:
                            sleep_time = 2 * (attempt + 1)
                            logger.warning(
                                f"Gemini API Rate limit hit. Retrying in {sleep_time}s..."
                            )
                            time.sleep(sleep_time)
                            continue
                    raise e

            # 파싱된 결과가 없으면 기본값 사용
            if not results:
                results = [{"score": 50, "reason": "LLM 분석 실패"} for _ in postings]

            return results

        except Exception as e:
            logger.error(f"Batch LLM evaluation failed: {e}", exc_info=True)
            return [{"score": 50, "reason": "LLM 분석 실패"} for _ in postings]

    @staticmethod
    def _evaluate_match_with_llm(
        posting: JobPosting, resume: Resume, prompt: RecommendationPrompt
    ) -> tuple[int, str]:
        """
        [Deprecated] 단일 공고 평가 (하위 호환성 유지)
        """
        results = RecommendationService._evaluate_match_batch_with_llm(
            [posting], resume, prompt
        )
        return results[0]["score"], results[0]["reason"]

    @staticmethod
    def get_skill_statistics(skill_name: str) -> Dict:
        """
        특정 스킬의 통계 정보 조회

        Args:
            skill_name: 스킬 이름

        Returns:
            스킬 통계 딕셔너리 (공고 수, 우대 공고 수, 인기도 등)
        """
        try:
            stats = graph_db_client.get_skill_statistics(skill_name)
            return stats
        except Exception as e:
            logger.error(
                f"Error getting skill statistics for {skill_name}: {e}", exc_info=True
            )
            return {
                "skill_name": skill_name,
                "required_count": 0,
                "preferred_count": 0,
                "total_count": 0,
            }

    @staticmethod
    def get_recommendation(recommendation_id: int) -> Optional[JobRecommendation]:
        """
        추천 조회

        Args:
            recommendation_id: 추천 ID

        Returns:
            JobRecommendation 객체 또는 None
        """
        try:
            return JobRecommendation.objects.get(id=recommendation_id)
        except JobRecommendation.DoesNotExist:
            logger.warning(f"JobRecommendation {recommendation_id} not found")
            return None

    @staticmethod
    def get_recommendations_by_user(user_id: int) -> List[JobRecommendation]:
        """
        사용자의 저장된 추천 목록 조회

        Args:
            user_id: 사용자 ID

        Returns:
            JobRecommendation 쿼리셋
        """
        return JobRecommendation.objects.filter(user_id=user_id)

    @staticmethod
    def create_recommendation(data: Dict) -> JobRecommendation:
        """
        추천 생성

        Args:
            data: 추천 데이터 딕셔너리

        Returns:
            생성된 JobRecommendation 객체
        """
        with transaction.atomic():
            recommendation = JobRecommendation.objects.create(**data)
            logger.info(
                f"Created JobRecommendation {recommendation.id} for user {recommendation.user_id}"
            )
            return recommendation

    @staticmethod
    def delete_recommendation(recommendation_id: int) -> bool:
        """
        추천 삭제

        Args:
            recommendation_id: 추천 ID

        Returns:
            삭제 성공 여부
        """
        recommendation = RecommendationService.get_recommendation(recommendation_id)
        if not recommendation:
            return False

        with transaction.atomic():
            recommendation.delete()
            logger.info(f"Deleted JobRecommendation {recommendation_id}")
            return True


# Backward compatibility: job/recommender.py 호환용
def get_recommendations(resume_id: int, limit: int = 10) -> List[Dict]:
    """
    [Backward Compatibility] job/recommender.py 호환용

    RecommendationService.get_recommendations()를 호출합니다.
    """
    return RecommendationService.get_recommendations(resume_id, limit)


def get_skill_statistics(skill_name: str) -> Dict:
    """
    [Backward Compatibility] job/recommender.py 호환용

    RecommendationService.get_skill_statistics()를 호출합니다.
    """
    return RecommendationService.get_skill_statistics(skill_name)

"""
Recommendation Service

AI-Free 실시간 채용 공고 추천 엔진
벡터 유사도 + 스킬 그래프 매칭을 결합한 하이브리드 추천 시스템
"""

import logging
import time
from typing import Dict, List, Optional

from common.application.result import Err, Ok
from django.db import transaction
from job.models import JobPosting
from recommendation.domain.scoring import (
    calculate_match_score_and_reason,
    calculate_position_similarity,
    map_position_to_category,
    normalize_position_text,
)
from recommendation.models import JobRecommendation, RecommendationPrompt
from resume.models import Resume

logger = logging.getLogger(__name__)
# Backward-compat globals (tests/mocking & legacy static methods use these names)
from common.adapters.chroma_vector_store import ChromaVectorStore
from common.adapters.gemini_recommendation_evaluator import (
    GeminiRecommendationEvaluator,
)
from common.adapters.neo4j_graph_store import Neo4jGraphStore
from recommendation.application.container import build_generate_recommendations_usecase

vector_store = ChromaVectorStore()
graph_store = Neo4jGraphStore()
recommendation_evaluator = GeminiRecommendationEvaluator()


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
            user_id = (
                Resume.objects.filter(id=resume_id)
                .values_list("user_id", flat=True)
                .first()
            )
            if not user_id:
                logger.error(f"Resume {resume_id} not found")
                return []

            usecase = build_generate_recommendations_usecase()
            result = usecase.execute(
                resume_id=resume_id, limit=limit, prompt_id=prompt_id
            )
            if isinstance(result, Err):
                logger.warning(result.message)
                return []

            assert isinstance(result, Ok)
            recommendation_obj_list = result.value

            # 이미 받은 추천 공고가 있다면 공고 삭제 후 다시 저장
            with transaction.atomic():
                JobRecommendation.objects.filter(user_id=user_id).delete()
                JobRecommendation.objects.bulk_create(recommendation_obj_list)

            return recommendation_obj_list[:limit]

        except Exception as e:
            logger.error(
                f"Error generating recommendations for resume {resume_id}: {e}",
                exc_info=True,
            )
            return []

    @staticmethod
    def _normalize_position_text(text: str) -> str:
        """[Deprecated] 도메인 함수로 이동."""
        return normalize_position_text(text)

    @staticmethod
    def _map_position_to_category(normalized_text: str) -> str:
        """[Deprecated] 도메인 함수로 이동."""
        return map_position_to_category(normalized_text)

    @staticmethod
    def _calculate_position_similarity(user_position: str, job_position: str) -> float:
        """[Deprecated] 도메인 함수로 이동."""
        return calculate_position_similarity(user_position, job_position)

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
                posting_skills = graph_store.get_required_skills(posting_id=posting_id)
                match_count = len(user_skills & posting_skills) if posting_skills else 0
                skill_scores[posting_id] = match_count
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
                posting_skills = graph_store.get_required_skills(posting_id=posting_id)
                if posting_skills and (user_skills & posting_skills):
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
            return graph_store.get_postings_by_skills(
                user_skills=user_skills, limit=limit
            )

        except Exception as e:
            logger.warning(f"Error querying postings by skills: {e}", exc_info=True)
            return []

    @staticmethod
    def _calculate_match_score_and_reason(
        posting: JobPosting, user_skills: set, user_career_years: int
    ) -> tuple[int, str]:
        """[Deprecated] 도메인 함수로 이동."""
        return calculate_match_score_and_reason(
            posting=posting,
            user_skills=user_skills,
            user_career_years=user_career_years,
        )

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
        return recommendation_evaluator.evaluate_batch(
            postings=postings,
            resume=resume,
            prompt=prompt,
            search_contexts=search_contexts,
        )

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
            stats = graph_store.get_skill_statistics(skill_name=skill_name)
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

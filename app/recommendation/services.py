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
        resume_id: int, limit: int = 10, prompt_id: Optional[int] = None
    ) -> List[Dict]:
        """
        사용자에게 적합한 채용 공고 추천

        Args:
            resume_id: 이력서 ID
            limit: 반환할 추천 개수 (기본 10개)

        Returns:
            추천 공고 리스트 (각 항목은 posting_id, match_score, match_reason 포함)
        """
        try:
            # 1. Resume에서 스킬 및 경력 정보 추출
            resume = Resume.objects.get(id=resume_id)
            user_id = resume.user_id
            user_skills = set(resume.analysis_result.get("skills", []))
            user_career_years = resume.analysis_result.get("career_years", 0)

            if not user_skills:
                logger.warning(
                    f"Resume {resume_id} (User {user_id}) has no skills in analysis_result"
                )
                return []

            # 2. ChromaDB에서 벡터 유사도 기반 후보 조회 (50개)
            resumes_collection = vector_db_client.get_or_create_collection("resumes")
            job_postings_collection = vector_db_client.get_or_create_collection(
                "job_postings"
            )

            # 사용자 이력서 벡터 조회 (Vector DB ID는 resume_id 사용)
            resume_vector = resumes_collection.get(
                ids=[str(resume_id)], include=["embeddings"]
            )

            # 임베딩 검증 (numpy 배열 대응)
            embeddings = resume_vector.get("embeddings") if resume_vector else None
            if embeddings is None or (
                hasattr(embeddings, "__len__") and len(embeddings) == 0
            ):
                logger.warning(f"No embedding found for user {user_id}")
                return []

            # 유사한 공고 50개 조회
            query_results = job_postings_collection.query(
                query_embeddings=embeddings, n_results=50
            )

            # 결과 검증 (numpy 배열 대응)
            result_ids = query_results.get("ids") if query_results else None
            if result_ids is None or (
                hasattr(result_ids, "__len__") and len(result_ids) == 0
            ):
                logger.info(f"No job postings found for user {user_id}")
                return []

            candidate_posting_ids = [int(pid) for pid in result_ids[0]]

            # 3. Neo4j로 스킬 그래프 매칭하여 100개로 정제
            matched_postings = RecommendationService._filter_by_skill_graph(
                candidate_posting_ids, user_skills
            )[:100]

            if not matched_postings:
                logger.info(f"No skill-matched postings for user {user_id}")
                return []

            # 4. 각 공고에 대해 match_score 계산 및 match_reason 생성
            recommendations = []

            # LLM 평가가 필요한 공고 수집
            postings_to_evaluate = []
            if prompt_id:
                for posting_id in matched_postings:
                    try:
                        posting = JobPosting.objects.get(posting_id=posting_id)
                        postings_to_evaluate.append(posting)
                    except JobPosting.DoesNotExist:
                        continue

                # 일괄 평가 수행
                if postings_to_evaluate:
                    prompt = RecommendationPrompt.objects.get(id=prompt_id)
                    batch_results = (
                        RecommendationService._evaluate_match_batch_with_llm(
                            postings_to_evaluate, resume, prompt
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
        postings: List[JobPosting], resume: Resume, prompt: RecommendationPrompt
    ) -> List[Dict]:
        """
        LLM을 사용하여 여러 공고와 이력서 간의 매칭 평가 (일괄 처리)

        Args:
            postings: 채용 공고 객체 리스트
            resume: 이력서 객체
            prompt: 사용할 프롬프트 객체

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

            # 공고 목록 요약
            jobs_text = ""
            for idx, posting in enumerate(postings):
                jobs_text += f"""
                [Job {idx+1}]
                ID: {posting.posting_id}
                Company: {posting.company_name}
                Position: {posting.position}
                Main Tasks: {posting.main_tasks}
                Requirements: {posting.requirements}
                Preferred: {posting.preferred_points}
                -------------------
                """

            # 프롬프트 구성
            full_prompt = f"""
            {prompt.content}

            [Candidate Resume Summary]
            {resume_summary}
            Skills: {skills}

            [Job Postings]
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

            # 재시도 로직
            max_retries = 3
            response = None

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

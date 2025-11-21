"""
Search Service

벡터 유사도 기반 검색 서비스
"""

import json
from typing import Dict, List

from common.graph_db import graph_db_client
from common.vector_db import vector_db_client
from django.db.models import Case, When
from job.models import JobPosting


class SearchService:
    """
    검색 서비스

    ChromaDB 벡터 유사도 검색을 제공합니다.
    """

    @staticmethod
    def vector_search(query_text: str, n_results: int = 20) -> List[Dict]:
        """
        주어진 쿼리 텍스트와 의미적으로 유사한 채용 공고를 벡터 DB에서 검색합니다.

        Args:
            query_text: 검색 쿼리 텍스트 (예: 이력서 요약, 스킬 키워드 등)
            n_results: 반환할 결과 수 (기본 20개)

        Returns:
            채용 공고 리스트 (딕셔너리 형태)
        """
        # 1. Vector DB에서 유사 공고 ID 검색
        collection = vector_db_client.get_or_create_collection("job_postings")
        query_result = vector_db_client.query(
            collection=collection,
            query_texts=[query_text],
            n_results=n_results,
        )

        posting_ids = query_result["ids"][0]
        if not posting_ids:
            return []

        # 2. ID를 사용하여 PostgreSQL에서 전체 공고 정보 조회
        # ChromaDB는 ID를 문자열로 저장하므로 정수형으로 변환
        int_posting_ids = [int(pid) for pid in posting_ids]

        # 3. 순서를 보장하면서 조회 (유사도 순서 유지)
        preserved_order = Case(
            *[When(posting_id=pk, then=pos) for pos, pk in enumerate(int_posting_ids)]
        )
        query_set = JobPosting.objects.filter(posting_id__in=int_posting_ids).order_by(
            preserved_order
        )

        # 4. 필요한 필드만 추출
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
                "skills_required",
                "skills_preferred",
            )
        )

        return filtered_postings

    @staticmethod
    def hybrid_search(
        query_text: str, user_skills: List[str], n_results: int = 20
    ) -> List[Dict]:
        """
        Vector DB와 Graph DB를 결합한 2단계 하이브리드 검색

        1단계: Vector DB에서 의미 기반 검색 (50개)
        2단계: Graph DB에서 스킬 기반 필터링 (n_results개)

        Args:
            query_text: 검색 쿼리 텍스트
            user_skills: 사용자 보유 스킬 리스트
            n_results: 최종 반환할 결과 수

        Returns:
            스킬 매칭된 채용 공고 리스트
        """
        # 1단계: Vector DB에서 더 많은 후보 검색 (50개)
        initial_candidates = 50
        collection = vector_db_client.get_or_create_collection("job_postings")
        query_result = vector_db_client.query(
            collection=collection,
            query_texts=[query_text],
            n_results=initial_candidates,
        )

        posting_ids = query_result["ids"][0]
        if not posting_ids:
            return []

        int_posting_ids = [int(pid) for pid in posting_ids]

        # 2단계: 스킬이 제공된 경우 Graph DB에서 스킬 매칭 필터링
        if user_skills:
            matched_postings = []
            for posting_id in int_posting_ids:
                # Neo4j에서 해당 공고의 필수 스킬 조회
                query = """
                MATCH (jp:JobPosting {posting_id: $posting_id})-[:REQUIRES_SKILL]->(skill:Skill)
                RETURN skill.name AS skill_name
                """
                result = graph_db_client.execute_query(
                    query, {"posting_id": posting_id}
                )

                if result:
                    posting_skills = {record["skill_name"] for record in result}
                    # 사용자 스킬과 매칭되는 경우만 포함
                    if set(user_skills) & posting_skills:
                        match_count = len(set(user_skills) & posting_skills)
                        matched_postings.append((posting_id, match_count))

            # 스킬 매칭 수 기준 정렬
            matched_postings.sort(key=lambda x: x[1], reverse=True)
            final_ids = [pid for pid, _ in matched_postings[:n_results]]

            # 매칭 결과가 없으면 fallback: Vector 검색 상위 n_results개
            if not final_ids:
                final_ids = int_posting_ids[:n_results]
        else:
            # 스킬 정보가 없으면 Vector 검색 상위 n_results개
            final_ids = int_posting_ids[:n_results]

        if not final_ids:
            return []

        # 3. PostgreSQL에서 공고 상세 정보 조회
        preserved_order = Case(
            *[When(posting_id=pk, then=pos) for pos, pk in enumerate(final_ids)]
        )
        query_set = JobPosting.objects.filter(posting_id__in=final_ids).order_by(
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
                "skills_required",
                "skills_preferred",
            )
        )

        return filtered_postings


# Backward Compatibility: agent.tools에서 사용하던 함수 형태
def vector_search_job_postings(query_text: str, n_results: int = 20) -> str:
    """
    [Backward Compatibility] agent.tools.vector_search_job_postings_tool 호환용

    SearchService.vector_search()를 호출하고 JSON 문자열로 반환합니다.
    """
    results = SearchService.vector_search(query_text, n_results)
    return json.dumps(results, ensure_ascii=False, default=str)


def hybrid_search_job_postings(
    query_text: str, user_skills: List[str], n_results: int = 20
) -> str:
    """
    [Backward Compatibility] agent.tools.hybrid_search_job_postings_tool 호환용

    SearchService.hybrid_search()를 호출하고 JSON 문자열로 반환합니다.
    """
    results = SearchService.hybrid_search(query_text, user_skills, n_results)
    return json.dumps(results, ensure_ascii=False, default=str)

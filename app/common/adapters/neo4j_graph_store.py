from __future__ import annotations

from common.graph_db import GraphDBClient


class Neo4jGraphStore:
    """
    Neo4j(Graph DB) 어댑터.

    - 내부적으로는 기존 `common.graph_db.graph_db_client`를 그대로 사용합니다.
    """

    def upsert_job_posting(
        self,
        *,
        posting_id: int,
        position: str,
        company_name: str,
        skills_required: list[str],
    ) -> None:
        if not skills_required:
            return
        GraphDBClient.get_instance().add_job_posting(
            posting_id=posting_id,
            position=position,
            company_name=company_name,
            skills=skills_required,
        )

    def get_required_skills(self, *, posting_id: int) -> set[str]:
        query = """
        MATCH (jp:JobPosting {posting_id: $posting_id})-[:REQUIRES_SKILL]->(skill:Skill)
        RETURN skill.name AS skill_name
        """
        result = GraphDBClient.get_instance().execute_query(
            query, {"posting_id": posting_id}
        )
        return {record["skill_name"] for record in result} if result else set()

    def get_postings_by_skills(
        self, *, user_skills: set[str], limit: int = 50
    ) -> list[int]:
        if not user_skills:
            return []
        query = """
        MATCH (jp:JobPosting)-[:REQUIRES_SKILL]->(skill:Skill)
        WHERE skill.name IN $user_skills
        RETURN jp.posting_id AS posting_id, count(skill) as match_count
        ORDER BY match_count DESC, jp.posting_id DESC
        LIMIT $limit
        """
        result = GraphDBClient.get_instance().execute_query(
            query, {"user_skills": list(user_skills), "limit": limit}
        )
        if not result:
            return []
        return [record["posting_id"] for record in result if "posting_id" in record]

    def get_skill_statistics(self, *, skill_name: str | None = None) -> dict:
        return GraphDBClient.get_instance().get_skill_statistics(skill_name)

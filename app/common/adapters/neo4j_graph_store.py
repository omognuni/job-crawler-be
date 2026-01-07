from __future__ import annotations

from common.graph_db import graph_db_client


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
        graph_db_client.add_job_posting(
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
        result = graph_db_client.execute_query(query, {"posting_id": posting_id})
        return {record["skill_name"] for record in result} if result else set()

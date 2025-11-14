from django.conf import settings
from neo4j import GraphDatabase


class GraphDBClient:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def execute_query(self, query, parameters=None):
        with self._driver.session() as session:
            result = session.run(query, parameters)
            return [record for record in result]

    def add_job_posting(self, posting_id, position, company_name, skills):
        with self._driver.session() as session:
            session.execute_write(
                self._create_job_posting_and_relations,
                posting_id,
                position,
                company_name,
                skills,
            )

    @staticmethod
    def _create_job_posting_and_relations(
        tx, posting_id, position, company_name, skills
    ):
        # Create or merge company
        tx.run("MERGE (c:Company {name: $company_name})", company_name=company_name)

        # Create or merge job posting and link to company
        tx.run(
            """
            MERGE (j:JobPosting {posting_id: $posting_id})
            ON CREATE SET j.position = $position
            WITH j
            MATCH (c:Company {name: $company_name})
            MERGE (j)-[:POSTED_BY]->(c)
            """,
            posting_id=posting_id,
            position=position,
            company_name=company_name,
        )

        # Create or merge skills and link to job posting
        for skill in skills:
            tx.run(
                """
                MERGE (s:Skill {name: $skill})
                WITH s
                MATCH (j:JobPosting {posting_id: $posting_id})
                MERGE (j)-[:REQUIRES_SKILL]->(s)
                """,
                skill=skill,
                posting_id=posting_id,
            )

    def get_jobs_related_to_skill(self, skill_name: str, limit: int = 10) -> list[int]:
        """
        특정 기술과 관련된 다른 채용 공고를 추천합니다.
        1. 해당 기술을 요구하는 회사를 찾습니다.
        2. 해당 회사들의 다른 채용 공고를 추천합니다.
        """
        query = """
        MATCH (s:Skill {name: $skill_name})<-[:REQUIRES_SKILL]-(j:JobPosting)-[:POSTED_BY]->(c:Company)
        WITH c, j
        MATCH (c)<-[:POSTED_BY]-(related_job:JobPosting)
        WHERE j <> related_job
        RETURN DISTINCT related_job.posting_id AS posting_id
        LIMIT $limit
        """
        with self._driver.session() as session:
            result = session.run(query, skill_name=skill_name, limit=limit)
            return [record["posting_id"] for record in result]

    def filter_postings_by_skills(
        self, posting_ids: list[int], user_skills: list[str], limit: int = 20
    ) -> list[dict]:
        """
        Vector 검색 결과를 스킬 매칭으로 재필터링합니다.

        Args:
            posting_ids: Vector 검색으로 찾은 공고 ID 리스트
            user_skills: 사용자가 보유한 스킬 리스트
            limit: 반환할 최대 공고 수

        Returns:
            스킬 매칭 점수가 높은 순서로 정렬된 공고 ID와 매칭 정보 리스트
        """
        if not posting_ids or not user_skills:
            return []

        query = """
        UNWIND $posting_ids AS pid
        MATCH (j:JobPosting {posting_id: pid})
        OPTIONAL MATCH (j)-[:REQUIRES_SKILL]->(s:Skill)
        WHERE s.name IN $user_skills
        WITH j, COUNT(DISTINCT s) AS matched_skills, COLLECT(DISTINCT s.name) AS matched_skill_names
        OPTIONAL MATCH (j)-[:REQUIRES_SKILL]->(all_skills:Skill)
        WITH j, matched_skills, matched_skill_names, COUNT(DISTINCT all_skills) AS total_skills
        WHERE matched_skills > 0
        RETURN j.posting_id AS posting_id,
               matched_skills,
               matched_skill_names,
               total_skills,
               toFloat(matched_skills) / toFloat(total_skills) AS match_ratio
        ORDER BY matched_skills DESC, match_ratio DESC
        LIMIT $limit
        """

        with self._driver.session() as session:
            result = session.run(
                query, posting_ids=posting_ids, user_skills=user_skills, limit=limit
            )
            return [
                {
                    "posting_id": record["posting_id"],
                    "matched_skills": record["matched_skills"],
                    "matched_skill_names": record["matched_skill_names"],
                    "total_skills": record["total_skills"],
                    "match_ratio": record["match_ratio"],
                }
                for record in result
            ]


# Singleton instance
# TODO: Move credentials to settings.py
graph_db_client = GraphDBClient("bolt://neo4j:7687", "neo4j", "password")

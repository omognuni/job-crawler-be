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


# Singleton instance
# TODO: Move credentials to settings.py
graph_db_client = GraphDBClient("bolt://neo4j:7687", "neo4j", "password")

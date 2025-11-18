from functools import lru_cache

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

    @lru_cache(maxsize=1)
    def get_all_skills(self) -> list[str]:
        """
        Neo4j에 저장된 모든 스킬 이름을 조회합니다.
        결과는 캐시되어 반복 호출 시 빠르게 반환됩니다.

        Returns:
            스킬 이름 리스트 (정렬됨)
        """
        query = """
        MATCH (s:Skill)
        RETURN s.name AS skill_name
        ORDER BY s.name
        """

        with self._driver.session() as session:
            result = session.run(query)
            return [record["skill_name"] for record in result]

    def get_skill_statistics(self, skill_name: str = None) -> dict:
        """
        Neo4j에 저장된 스킬 통계를 반환합니다.

        Args:
            skill_name: 특정 스킬 이름 (None이면 전체 통계 반환)

        Returns:
            skill_name이 있는 경우:
            {
                "skill_name": 스킬 이름,
                "required_count": 필수로 요구하는 공고 수,
                "preferred_count": 우대로 요구하는 공고 수,
                "total_count": 전체 공고 수
            }

            skill_name이 없는 경우:
            {
                "total_skills": 총 스킬 수,
                "total_postings": 총 공고 수,
                "most_required_skills": 가장 많이 요구되는 스킬 Top 10
            }
        """
        if skill_name:
            # 특정 스킬의 통계
            query = """
            MATCH (s:Skill {name: $skill_name})
            OPTIONAL MATCH (s)<-[:REQUIRES]-(jp_req:JobPosting)
            OPTIONAL MATCH (s)<-[:PREFERS]-(jp_pref:JobPosting)
            RETURN s.name AS skill_name,
                   COUNT(DISTINCT jp_req) AS required_count,
                   COUNT(DISTINCT jp_pref) AS preferred_count,
                   COUNT(DISTINCT jp_req) + COUNT(DISTINCT jp_pref) AS total_count
            """

            with self._driver.session() as session:
                result = session.run(query, skill_name=skill_name)
                record = result.single()

                if not record or not record["skill_name"]:
                    return {
                        "skill_name": skill_name,
                        "required_count": 0,
                        "preferred_count": 0,
                        "total_count": 0,
                    }

                return {
                    "skill_name": record["skill_name"],
                    "required_count": record["required_count"],
                    "preferred_count": record["preferred_count"],
                    "total_count": record["total_count"],
                }
        else:
            # 전체 통계
            query = """
            MATCH (s:Skill)<-[:REQUIRES_SKILL]-(j:JobPosting)
            WITH s, COUNT(j) AS posting_count
            RETURN COUNT(DISTINCT s) AS total_skills,
                   COLLECT({
                       skill: s.name,
                       count: posting_count
                   }) AS skill_usage
            """

            with self._driver.session() as session:
                result = session.run(query)
                record = result.single()

                if not record:
                    return {
                        "total_skills": 0,
                        "total_postings": 0,
                        "most_required_skills": [],
                    }

                skill_usage = record["skill_usage"]
                # 사용 빈도순 정렬
                sorted_skills = sorted(
                    skill_usage, key=lambda x: x["count"], reverse=True
                )

                return {
                    "total_skills": record["total_skills"],
                    "most_required_skills": sorted_skills[:10],
                }

    def create_skill_index(self):
        """
        Skill 노드에 인덱스를 생성하여 쿼리 성능을 향상시킵니다.
        애플리케이션 시작 시 한 번 호출하면 됩니다.
        """
        index_query = """
        CREATE INDEX skill_name_index IF NOT EXISTS
        FOR (s:Skill)
        ON (s.name)
        """

        with self._driver.session() as session:
            session.run(index_query)


# Singleton instance
# Credentials loaded from environment variables via settings
def _get_graph_db_client():
    """Factory function to create GraphDB client with settings"""
    neo4j_uri = settings.NEO4J_URI
    neo4j_user = settings.NEO4J_USER
    neo4j_password = settings.NEO4J_PASSWORD
    return GraphDBClient(neo4j_uri, neo4j_user, neo4j_password)


graph_db_client = _get_graph_db_client()

"""
Search App Tests

검색 서비스 및 뷰 테스트
"""

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase
from job.models import JobPosting
from rest_framework.test import APITestCase
from search.services import (
    SearchService,
    hybrid_search_job_postings,
    vector_search_job_postings,
)


class TestSearchService(TestCase):
    """SearchService 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        self.test_job = JobPosting.objects.create(
            posting_id=1,
            url="https://example.com/job/1",
            company_name="Test Company",
            position="백엔드 개발자",
            main_tasks="Django 개발",
            requirements="Python 3년 이상",
            preferred_points="FastAPI 경험자 우대",
            location="서울",
            district="강남구",
            employment_type="정규직",
            career_min=3,
            career_max=5,
            skills_required=["Python", "Django"],
            skills_preferred=["FastAPI", "PostgreSQL"],
        )

    @patch("search.services.vector_db_client")
    def test_vector_search_success(self, mock_vector_db):
        """벡터 검색 성공 케이스"""
        # Mock ChromaDB response
        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection
        mock_vector_db.query.return_value = {"ids": [["1"]]}

        # 검색 실행
        results = SearchService.vector_search("Python 개발자", n_results=10)

        # 검증
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["posting_id"], 1)
        self.assertEqual(results[0]["company_name"], "Test Company")
        self.assertEqual(results[0]["position"], "백엔드 개발자")

        # ChromaDB 호출 확인
        mock_vector_db.get_or_create_collection.assert_called_once_with("job_postings")
        mock_vector_db.query.assert_called_once()

    @patch("search.services.vector_db_client")
    def test_vector_search_empty_results(self, mock_vector_db):
        """벡터 검색 결과 없음"""
        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection
        mock_vector_db.query.return_value = {"ids": [[]]}

        results = SearchService.vector_search("존재하지 않는 키워드", n_results=10)

        self.assertEqual(results, [])

    @patch("search.services.graph_db_client")
    @patch("search.services.vector_db_client")
    def test_hybrid_search_with_skill_match(self, mock_vector_db, mock_graph_db):
        """하이브리드 검색 - 스킬 매칭 성공"""
        # Mock ChromaDB response
        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection
        mock_vector_db.query.return_value = {"ids": [["1"]]}

        # Mock Neo4j response
        mock_graph_db.execute_query.return_value = [
            {"skill_name": "Python"},
            {"skill_name": "Django"},
        ]

        # 검색 실행
        results = SearchService.hybrid_search(
            query_text="Python 백엔드 개발자",
            user_skills=["Python", "Django"],
            n_results=10,
        )

        # 검증
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["posting_id"], 1)

        # Graph DB 호출 확인
        mock_graph_db.execute_query.assert_called()

    @patch("search.services.vector_db_client")
    def test_hybrid_search_no_skills(self, mock_vector_db):
        """하이브리드 검색 - 스킬 정보 없음 (fallback to vector)"""
        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection
        mock_vector_db.query.return_value = {"ids": [["1"]]}

        results = SearchService.hybrid_search(
            query_text="백엔드 개발자",
            user_skills=[],
            n_results=10,
        )

        # 스킬이 없어도 벡터 검색 결과는 반환
        self.assertEqual(len(results), 1)


class TestSearchBackwardCompatibility(TestCase):
    """Backward Compatibility 함수 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        JobPosting.objects.create(
            posting_id=1,
            url="https://example.com/job/1",
            company_name="Test Company",
            position="백엔드 개발자",
            main_tasks="Django 개발",
            requirements="Python 3년 이상",
            preferred_points="",
            location="서울",
            district="강남구",
            employment_type="정규직",
            career_min=3,
            career_max=5,
            skills_required=["Python", "Django"],
            skills_preferred=["FastAPI"],
        )

    @patch("search.services.vector_db_client")
    def test_vector_search_job_postings_returns_json_string(self, mock_vector_db):
        """vector_search_job_postings는 JSON 문자열 반환"""
        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection
        mock_vector_db.query.return_value = {"ids": [["1"]]}

        result = vector_search_job_postings("Python", n_results=10)

        # JSON 문자열인지 확인
        self.assertIsInstance(result, str)

        # 파싱 가능한지 확인
        parsed = json.loads(result)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["posting_id"], 1)

    @patch("search.services.graph_db_client")
    @patch("search.services.vector_db_client")
    def test_hybrid_search_job_postings_returns_json_string(
        self, mock_vector_db, mock_graph_db
    ):
        """hybrid_search_job_postings는 JSON 문자열 반환"""
        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection
        mock_vector_db.query.return_value = {"ids": [["1"]]}
        mock_graph_db.execute_query.return_value = [{"skill_name": "Python"}]

        result = hybrid_search_job_postings(
            query_text="Python 개발자",
            user_skills=["Python"],
            n_results=10,
        )

        # JSON 문자열인지 확인
        self.assertIsInstance(result, str)

        # 파싱 가능한지 확인
        parsed = json.loads(result)
        self.assertEqual(len(parsed), 1)


class TestSearchAPI(APITestCase):
    """Search API 엔드포인트 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        JobPosting.objects.create(
            posting_id=1,
            url="https://example.com/job/1",
            company_name="Test Company",
            position="백엔드 개발자",
            main_tasks="Django 개발",
            requirements="Python 3년 이상",
            preferred_points="",
            location="서울",
            district="강남구",
            employment_type="정규직",
            career_min=3,
            career_max=5,
            skills_required=["Python", "Django"],
            skills_preferred=["FastAPI"],
        )

    @patch("search.services.vector_db_client")
    def test_job_search_view_success(self, mock_vector_db):
        """JobSearchView GET 요청 성공"""
        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection
        mock_vector_db.query.return_value = {"ids": [["1"]]}

        response = self.client.get("/api/v1/search/?query=Python개발자")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["posting_id"], 1)

    def test_job_search_view_missing_query(self):
        """JobSearchView query 파라미터 없음"""
        response = self.client.get("/api/v1/search/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)

    @patch("search.services.graph_db_client")
    @patch("search.services.vector_db_client")
    def test_hybrid_search_view_success(self, mock_vector_db, mock_graph_db):
        """HybridSearchView POST 요청 성공"""
        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection
        mock_vector_db.query.return_value = {"ids": [["1"]]}
        mock_graph_db.execute_query.return_value = [{"skill_name": "Python"}]

        response = self.client.post(
            "/api/v1/search/hybrid/",
            data={
                "query": "Python 백엔드 개발자",
                "skills": ["Python", "Django"],
                "limit": 10,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("query", response.data)
        self.assertIn("skills", response.data)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)

    def test_hybrid_search_view_missing_query(self):
        """HybridSearchView query 파라미터 없음"""
        response = self.client.post(
            "/api/v1/search/hybrid/",
            data={"skills": ["Python"]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)

    def test_hybrid_search_view_invalid_skills(self):
        """HybridSearchView skills가 리스트가 아닌 경우"""
        response = self.client.post(
            "/api/v1/search/hybrid/",
            data={"query": "Python", "skills": "Python,Django"},  # 문자열
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)

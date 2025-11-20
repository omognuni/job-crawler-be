"""
Tests for SearchService

검색 서비스 로직 테스트
"""

from unittest.mock import MagicMock, patch

import pytest
from job.models import JobPosting
from search.services import SearchService


@pytest.mark.django_db
class TestSearchService:
    """SearchService 단위 테스트"""

    @patch("search.services.vector_db_client")
    def test_vector_search_success(self, mock_vector_db):
        """벡터 검색 성공"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=1,
            url="https://example.com/job/1",
            company_name="Test Company",
            position="Backend Developer",
            main_tasks="Python development",
            requirements="Python, Django",
            preferred_points="AWS",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=5,
            skills_required=["Python", "Django"],
        )

        # Mock ChromaDB
        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection
        mock_vector_db.query.return_value = {"ids": [["1"]]}

        # When
        results = SearchService.vector_search("Python backend developer", n_results=10)

        # Then
        assert len(results) > 0
        assert results[0]["posting_id"] == 1

    @patch("search.services.vector_db_client")
    def test_vector_search_no_results(self, mock_vector_db):
        """벡터 검색 결과 없음"""
        # Given
        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection
        mock_vector_db.query.return_value = {"ids": [[]]}

        # When
        results = SearchService.vector_search("nonexistent query", n_results=10)

        # Then
        assert results == []

    @patch("search.services.graph_db_client")
    @patch("search.services.vector_db_client")
    def test_hybrid_search_with_skills(self, mock_vector_db, mock_graph_db):
        """스킬 기반 하이브리드 검색"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=2,
            url="https://example.com/job/2",
            company_name="Company B",
            position="Backend Developer",
            main_tasks="Development",
            requirements="Python, Django",
            preferred_points="AWS",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=5,
            skills_required=["Python", "Django"],
        )

        # Mock ChromaDB
        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection
        mock_vector_db.query.return_value = {"ids": [["2"]]}

        # Mock Neo4j
        mock_graph_db.execute_query.return_value = [
            {"skill_name": "Python"},
            {"skill_name": "Django"},
        ]

        user_skills = ["Python", "Django"]

        # When
        results = SearchService.hybrid_search(
            "Backend developer", user_skills, n_results=10
        )

        # Then
        assert len(results) > 0
        assert results[0]["posting_id"] == 2

    @patch("search.services.vector_db_client")
    def test_hybrid_search_without_skills(self, mock_vector_db):
        """스킬 없이 하이브리드 검색 (벡터 검색만)"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=3,
            url="https://example.com/job/3",
            company_name="Company C",
            position="Developer",
            main_tasks="Dev",
            requirements="Skills",
            preferred_points="Preferred",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=1,
            career_max=3,
        )

        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection
        mock_vector_db.query.return_value = {"ids": [["3"]]}

        # When
        results = SearchService.hybrid_search("Developer", [], n_results=10)

        # Then
        assert len(results) > 0
        assert results[0]["posting_id"] == 3

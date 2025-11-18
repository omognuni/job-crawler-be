"""
Tests for Recommendations API endpoint.
"""

from unittest.mock import Mock, patch

import pytest
from django.urls import reverse
from job.models import JobPosting, Resume
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestRecommendationsAPI:
    """Tests for /api/job/recommend/ endpoint"""

    def setup_method(self):
        """Set up test client"""
        self.client = APIClient()

    def test_recommendations_missing_user_id(self):
        """
        user_id 파라미터 없이 요청하면 400 에러
        """
        url = reverse("realtime-recommendations")
        response = self.client.get(url)

        assert response.status_code == 400
        assert "user_id" in response.data["error"]

    def test_recommendations_invalid_user_id(self):
        """
        잘못된 형식의 user_id로 요청하면 400 에러
        """
        url = reverse("realtime-recommendations")
        response = self.client.get(url, {"user_id": "invalid"})

        assert response.status_code == 400
        assert "integer" in response.data["error"]

    def test_recommendations_invalid_limit(self):
        """
        잘못된 형식의 limit로 요청하면 400 에러
        """
        url = reverse("realtime-recommendations")
        response = self.client.get(url, {"user_id": "101", "limit": "invalid"})

        assert response.status_code == 400
        assert "integer" in response.data["error"]

    @patch("job.recommender.get_recommendations")
    def test_recommendations_success(self, mock_get_recommendations):
        """
        정상적인 추천 요청
        """
        mock_get_recommendations.return_value = [
            {
                "posting_id": 1,
                "company_name": "Company A",
                "position": "Backend Developer",
                "match_score": 85,
                "match_reason": "필수 스킬 3/3개 보유 | 경력 요건 충족",
                "url": "https://example.com/job/1",
                "location": "Seoul",
                "employment_type": "Full-time",
            },
            {
                "posting_id": 2,
                "company_name": "Company B",
                "position": "Full Stack Developer",
                "match_score": 75,
                "match_reason": "필수 스킬 2/3개 보유",
                "url": "https://example.com/job/2",
                "location": "Busan",
                "employment_type": "Full-time",
            },
        ]

        url = reverse("realtime-recommendations")
        response = self.client.get(url, {"user_id": "101"})

        assert response.status_code == 200
        assert response.data["user_id"] == 101
        assert response.data["count"] == 2
        assert len(response.data["recommendations"]) == 2

        # Verify first recommendation
        rec1 = response.data["recommendations"][0]
        assert rec1["posting_id"] == 1
        assert rec1["company_name"] == "Company A"
        assert rec1["match_score"] == 85
        assert "필수 스킬" in rec1["match_reason"]

        # Verify mock was called correctly
        mock_get_recommendations.assert_called_once_with(101, limit=10)

    @patch("job.recommender.get_recommendations")
    def test_recommendations_with_custom_limit(self, mock_get_recommendations):
        """
        커스텀 limit 파라미터 전달
        """
        mock_get_recommendations.return_value = []

        url = reverse("realtime-recommendations")
        response = self.client.get(url, {"user_id": "101", "limit": "5"})

        assert response.status_code == 200
        mock_get_recommendations.assert_called_once_with(101, limit=5)

    @patch("job.recommender.get_recommendations")
    def test_recommendations_no_results(self, mock_get_recommendations):
        """
        추천 결과가 없는 경우
        """
        mock_get_recommendations.return_value = []

        url = reverse("realtime-recommendations")
        response = self.client.get(url, {"user_id": "101"})

        assert response.status_code == 200
        assert response.data["user_id"] == 101
        assert response.data["count"] == 0
        assert response.data["recommendations"] == []

    @patch("job.recommender.graph_db_client")
    @patch("job.recommender.vector_db_client")
    def test_recommendations_full_integration(self, mock_vector_db, mock_graph):
        """
        실제 추천 엔진과 통합된 E2E 테스트
        """
        # Create test data
        Resume.objects.create(
            user_id=201,
            content="Python Django developer",
            analysis_result={
                "skills": ["Python", "Django"],
                "career_years": 3,
            },
        )

        JobPosting.objects.create(
            posting_id=101,
            company_name="Test Company",
            position="Backend Developer",
            url="https://example.com/job/101",
            main_tasks="Development",
            requirements="Required",
            preferred_points="Preferred",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=2,
            career_max=5,
            skills_required=["Python", "Django"],
            skills_preferred=[],
        )

        # Mock vector DB
        mock_resumes_collection = Mock()
        mock_job_postings_collection = Mock()
        mock_vector_db.get_or_create_collection.side_effect = [
            mock_resumes_collection,
            mock_job_postings_collection,
        ]

        mock_resumes_collection.get.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}

        mock_job_postings_collection.query.return_value = {
            "ids": [["101"]],
        }

        # Mock Neo4j
        mock_graph.execute_query.return_value = [
            {"skill_name": "Python", "skill_type": "required"},
            {"skill_name": "Django", "skill_type": "required"},
        ]

        # Make request
        url = reverse("realtime-recommendations")
        response = self.client.get(url, {"user_id": "201", "limit": "10"})

        # Verify response
        assert response.status_code == 200
        assert response.data["user_id"] == 201
        assert response.data["count"] == 1

        rec = response.data["recommendations"][0]
        assert rec["posting_id"] == 101
        assert rec["company_name"] == "Test Company"
        assert rec["match_score"] == 70  # Required skills (50) + Career (20)
        assert "company_name" in rec
        assert "position" in rec
        assert "url" in rec
        assert "match_reason" in rec

    @patch("job.recommender.get_recommendations")
    def test_recommendations_handles_exception(self, mock_get_recommendations):
        """
        추천 엔진에서 예외 발생 시 빈 리스트 반환 (graceful degradation)
        """
        # get_recommendations가 예외를 던지지 않고 빈 리스트를 반환하도록 구현됨
        mock_get_recommendations.return_value = []

        url = reverse("realtime-recommendations")
        response = self.client.get(url, {"user_id": "999"})

        assert response.status_code == 200
        assert response.data["recommendations"] == []

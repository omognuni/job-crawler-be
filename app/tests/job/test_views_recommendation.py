"""
Tests for JobRecommendationViewSet with new AI-Free recommendation engine.
"""

from unittest.mock import Mock, patch

import pytest
from django.urls import reverse
from job.models import JobPosting, JobRecommendation, Resume
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestJobRecommendationViewSet:
    """Tests for JobRecommendationViewSet"""

    def setup_method(self):
        """Set up test client"""
        self.client = APIClient()

    @patch("job.views.get_recommendations")
    def test_for_user_endpoint_success(self, mock_get_recommendations):
        """
        실시간 추천 엔드포인트 정상 작동 테스트
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

        url = reverse("recommendation-for-user", kwargs={"user_id": "101"})
        response = self.client.get(url)

        assert response.status_code == 200
        assert response.data["user_id"] == 101
        assert response.data["count"] == 2
        assert len(response.data["recommendations"]) == 2
        assert "response_time_seconds" in response.data

        # Verify first recommendation
        rec1 = response.data["recommendations"][0]
        assert rec1["posting_id"] == 1
        assert rec1["company_name"] == "Company A"
        assert rec1["match_score"] == 85

        # Verify mock was called correctly
        mock_get_recommendations.assert_called_once_with(101, limit=10)

    @patch("job.views.get_recommendations")
    def test_for_user_with_custom_limit(self, mock_get_recommendations):
        """
        커스텀 limit 파라미터 테스트
        """
        mock_get_recommendations.return_value = []

        url = reverse("recommendation-for-user", kwargs={"user_id": "101"})
        response = self.client.get(url, {"limit": "5"})

        assert response.status_code == 200
        mock_get_recommendations.assert_called_once_with(101, limit=5)

    def test_for_user_invalid_user_id(self):
        """
        잘못된 user_id 형식 테스트

        URL 패턴이 숫자만 허용하므로 ((?P<user_id>[0-9]+)),
        잘못된 형식의 user_id는 URL 매칭 단계에서 404가 발생합니다.
        """
        # URL 패턴이 숫자만 허용하므로 직접 테스트
        response = self.client.get("/api/v1/recommendations/for-user/invalid/")

        # URL 패턴 매칭 실패로 404 반환
        assert response.status_code == 404

    @patch("job.views.get_recommendations")
    def test_for_user_invalid_limit(self, mock_get_recommendations):
        """
        잘못된 limit 형식 테스트
        """
        url = reverse("recommendation-for-user", kwargs={"user_id": "101"})
        response = self.client.get(url, {"limit": "invalid"})

        assert response.status_code == 400
        assert "integer" in response.data["error"]

    @patch("job.views.get_recommendations")
    def test_for_user_no_recommendations(self, mock_get_recommendations):
        """
        추천 결과가 없는 경우
        """
        mock_get_recommendations.return_value = []

        url = reverse("recommendation-for-user", kwargs={"user_id": "101"})
        response = self.client.get(url)

        assert response.status_code == 200
        assert response.data["count"] == 0
        assert response.data["recommendations"] == []

    @patch("job.views.get_recommendations")
    @patch("job.views.logger")
    def test_for_user_logs_response_time(self, mock_logger, mock_get_recommendations):
        """
        응답 시간 로깅 확인
        """
        mock_get_recommendations.return_value = [
            {
                "posting_id": 1,
                "company_name": "Test Company",
                "position": "Developer",
                "match_score": 80,
                "match_reason": "Good match",
                "url": "https://example.com/job/1",
                "location": "Seoul",
                "employment_type": "Full-time",
            }
        ]

        url = reverse("recommendation-for-user", kwargs={"user_id": "101"})
        response = self.client.get(url)

        assert response.status_code == 200

        # Verify logging was called
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "user 101" in log_message
        assert "seconds" in log_message

    def test_list_recommendations_filter_by_user(self):
        """
        사용자별 저장된 추천 목록 필터링 테스트
        """
        # Create test data
        posting1 = JobPosting.objects.create(
            posting_id=1,
            company_name="Company A",
            position="Backend Developer",
            url="https://example.com/job/1",
            main_tasks="Development",
            requirements="Required",
            preferred_points="Preferred",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=2,
            career_max=5,
        )

        posting2 = JobPosting.objects.create(
            posting_id=2,
            company_name="Company B",
            position="Frontend Developer",
            url="https://example.com/job/2",
            main_tasks="Development",
            requirements="Required",
            preferred_points="Preferred",
            location="Busan",
            district="Haeundae",
            employment_type="Full-time",
            career_min=1,
            career_max=3,
        )

        # Create recommendations
        JobRecommendation.objects.create(
            user_id=101,
            job_posting=posting1,
            rank=1,
            match_score=85.0,
            match_reason="Good match",
        )

        JobRecommendation.objects.create(
            user_id=102,
            job_posting=posting2,
            rank=1,
            match_score=75.0,
            match_reason="Decent match",
        )

        # Test filtering
        url = reverse("recommendation-list")
        response = self.client.get(url, {"user_id": "101"})

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["user_id"] == 101

    def test_list_recommendations_invalid_user_id(self):
        """
        잘못된 user_id로 필터링 시 에러 반환
        """
        url = reverse("recommendation-list")
        response = self.client.get(url, {"user_id": "invalid"})

        assert response.status_code == 400
        assert "integer" in response.data["error"]

    def test_list_recommendations_all(self):
        """
        user_id 없이 전체 추천 목록 조회
        """
        url = reverse("recommendation-list")
        response = self.client.get(url)

        # Should return all recommendations without filtering
        assert response.status_code == 200
        assert isinstance(response.data, list)

    @patch("job.views.get_recommendations")
    def test_response_time_included_in_response(self, mock_get_recommendations):
        """
        응답 객체에 response_time_seconds 필드가 포함되어야 함
        """
        mock_get_recommendations.return_value = []

        url = reverse("recommendation-for-user", kwargs={"user_id": "101"})
        response = self.client.get(url)

        assert response.status_code == 200
        assert "response_time_seconds" in response.data
        assert isinstance(response.data["response_time_seconds"], (int, float))
        assert response.data["response_time_seconds"] >= 0

    @patch("job.recommender.graph_db_client")
    @patch("job.recommender.vector_db_client")
    def test_for_user_full_integration(self, mock_vector_db, mock_graph):
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
        url = reverse("recommendation-for-user", kwargs={"user_id": "201"})
        response = self.client.get(url, {"limit": "10"})

        # Verify response
        assert response.status_code == 200
        assert response.data["user_id"] == 201
        assert response.data["count"] == 1
        assert "response_time_seconds" in response.data

        rec = response.data["recommendations"][0]
        assert rec["posting_id"] == 101
        assert rec["company_name"] == "Test Company"
        assert rec["match_score"] == 70  # Required skills (50) + Career (20)

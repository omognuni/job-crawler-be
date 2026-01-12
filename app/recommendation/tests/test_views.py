"""
Tests for Recommendation Views

추천 API 엔드포인트 테스트
"""

from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from job.models import JobPosting
from recommendation.models import JobRecommendation
from rest_framework import status
from rest_framework.test import APIClient
from resume.models import Resume

User = get_user_model()


@pytest.mark.django_db
class TestJobRecommendationViewSet:
    """JobRecommendationViewSet API 테스트"""

    def setup_method(self):
        """각 테스트 전에 실행"""
        self.client = APIClient()
        # 테스트용 사용자 생성 및 인증
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)
        # API 키 인증 헤더 추가 (settings에서 가져옴)
        self.client.credentials(HTTP_X_API_KEY=settings.API_SECRET_KEY)

    def test_list_recommendations(self):
        """추천 목록 조회"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=1,
            url="https://example.com/job/1",
            company_name="Company",
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

        JobRecommendation.objects.create(
            user_id=1,
            job_posting=posting,
            rank=1,
            match_score=85,
            match_reason="Good match",
        )

        # When
        response = self.client.get("/api/v1/recommendations/?user_id=1")

        # Then
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    @patch("recommendation.views.RecommendationService")
    def test_for_user_real_time_recommendations(self, mock_service):
        """실시간 추천 생성"""
        # Given
        user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="testpass123"
        )
        Resume.objects.create(
            user=user2,
            content="Backend Developer",
            analysis_result={"skills": ["Python"], "career_years": 3},
        )

        mock_service.get_recommendations.return_value = [
            {
                "posting_id": 1,
                "company_name": "Test Company",
                "position": "Backend Developer",
                "match_score": 85,
                "match_reason": "Great match",
                "url": "https://example.com/job/1",
                "location": "Seoul",
                "employment_type": "Full-time",
            }
        ]

        # When
        response = self.client.get(f"/api/v1/recommendations/for-user/{user2.id}/")

        # Then
        assert response.status_code == status.HTTP_200_OK
        assert response.data["user_id"] == user2.id
        assert "recommendations" in response.data

    def test_create_recommendation(self):
        """추천 생성"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=2,
            url="https://example.com/job/2",
            company_name="Company",
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

        data = {
            "user_id": 3,
            "job_posting": posting.posting_id,
            "rank": 1,
            "match_score": 90.5,
            "match_reason": "Perfect match",
        }

        # When
        response = self.client.post("/api/v1/recommendations/", data, format="json")

        # Then
        assert response.status_code == status.HTTP_201_CREATED
        # 반올림(half-up): 90.5 -> 91
        assert response.data["match_score"] == 91

    def test_delete_recommendation(self):
        """추천 삭제"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=3,
            url="https://example.com/job/3",
            company_name="Company",
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

        recommendation = JobRecommendation.objects.create(
            user_id=4,
            job_posting=posting,
            rank=1,
            match_score=85,
            match_reason="Good match",
        )

        # When
        response = self.client.delete(f"/api/v1/recommendations/{recommendation.id}/")

        # Then
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not JobRecommendation.objects.filter(id=recommendation.id).exists()

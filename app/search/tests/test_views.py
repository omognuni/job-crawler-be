"""
Tests for Search Views

검색 API 엔드포인트 테스트
"""

from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestSearchViews:
    """Search API 테스트"""

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

    @patch("search.views.SearchService")
    def test_job_search_success(self, mock_service):
        """채용 공고 검색 성공"""
        # Given
        mock_service.vector_search.return_value = [
            {
                "posting_id": 1,
                "company_name": "Test Company",
                "position": "Backend Developer",
                "location": "Seoul",
            }
        ]

        # When
        response = self.client.get("/api/v1/search/?query=Python developer")

        # Then
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) > 0

    def test_job_search_missing_query(self):
        """쿼리 파라미터 없이 검색"""
        # When
        response = self.client.get("/api/v1/search/")

        # Then
        assert response.status_code == 400
        assert "error" in response.data

    @patch("search.views.SearchService")
    def test_hybrid_search_success(self, mock_service):
        """하이브리드 검색 성공"""
        # Given
        mock_service.hybrid_search.return_value = [
            {
                "posting_id": 1,
                "company_name": "Test Company",
                "position": "Backend Developer",
                "location": "Seoul",
            }
        ]

        data = {
            "query": "Backend developer",
            "skills": ["Python", "Django"],
            "limit": 20,
        }

        # When
        response = self.client.post("/api/v1/search/hybrid/", data, format="json")

        # Then
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        assert "query" in response.data
        assert "skills" in response.data

    def test_hybrid_search_missing_query(self):
        """쿼리 없이 하이브리드 검색"""
        # Given
        data = {"skills": ["Python"]}

        # When
        response = self.client.post("/api/v1/search/hybrid/", data, format="json")

        # Then
        assert response.status_code == 400

    def test_hybrid_search_invalid_skills_type(self):
        """잘못된 스킬 타입으로 하이브리드 검색"""
        # Given
        data = {
            "query": "Backend developer",
            "skills": "Python, Django",  # Should be a list
        }

        # When
        response = self.client.post("/api/v1/search/hybrid/", data, format="json")

        # Then
        assert response.status_code == 400

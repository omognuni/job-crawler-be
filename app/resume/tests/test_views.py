"""
Tests for Resume Views

이력서 API 엔드포인트 테스트
"""

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from resume.models import Resume

User = get_user_model()


@pytest.mark.django_db
class TestResumeViewSet:
    """ResumeViewSet API 테스트"""

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

    def test_list_resumes(self):
        """이력서 목록 조회"""
        # Given
        Resume.objects.create(
            user_id=1,
            content="Backend Developer with Python experience",
        )

        # When
        response = self.client.get("/api/v1/resumes/")

        # Then
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_retrieve_resume(self):
        """이력서 상세 조회"""
        # Given
        resume = Resume.objects.create(
            user_id=2,
            content="Frontend Developer with React experience",
        )

        # When
        response = self.client.get(f"/api/v1/resumes/{resume.user_id}/")

        # Then
        assert response.status_code == status.HTTP_200_OK
        assert response.data["user_id"] == 2

    def test_create_resume(self):
        """이력서 생성"""
        # Given
        data = {
            "user_id": 3,
            "content": "Data Engineer with Spark experience",
        }

        # When
        response = self.client.post("/api/v1/resumes/", data, format="json")

        # Then
        assert response.status_code == status.HTTP_201_CREATED
        assert Resume.objects.filter(user_id=3).exists()

    def test_update_resume(self):
        """이력서 수정"""
        # Given
        resume = Resume.objects.create(
            user_id=4,
            content="Old content",
        )

        data = {"content": "Updated content"}

        # When
        response = self.client.patch(
            f"/api/v1/resumes/{resume.user_id}/", data, format="json"
        )

        # Then
        assert response.status_code == status.HTTP_200_OK
        resume.refresh_from_db()
        assert resume.content == "Updated content"

    def test_delete_resume(self):
        """이력서 삭제"""
        # Given
        resume = Resume.objects.create(
            user_id=5,
            content="Content to delete",
        )

        # When
        response = self.client.delete(f"/api/v1/resumes/{resume.user_id}/")

        # Then
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Resume.objects.filter(user_id=5).exists()

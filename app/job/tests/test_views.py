"""
Tests for JobPosting Views

채용 공고 API 엔드포인트 테스트
"""

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from job.models import JobPosting
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestJobPostingViewSet:
    """JobPostingViewSet API 테스트"""

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

    def test_list_job_postings(self):
        """채용 공고 목록 조회"""
        # Given
        JobPosting.objects.create(
            posting_id=1,
            url="https://example.com/job/1",
            company_name="Company A",
            position="Backend Developer",
            main_tasks="Development",
            requirements="Python",
            preferred_points="Django",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=5,
        )

        # When
        response = self.client.get("/api/v1/jobs/")

        # Then
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_retrieve_job_posting(self):
        """채용 공고 상세 조회"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=2,
            url="https://example.com/job/2",
            company_name="Company B",
            position="Frontend Developer",
            main_tasks="Development",
            requirements="React",
            preferred_points="TypeScript",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=2,
            career_max=4,
        )

        # When
        response = self.client.get(f"/api/v1/jobs/{posting.posting_id}/")

        # Then
        assert response.status_code == status.HTTP_200_OK
        assert response.data["posting_id"] == 2
        assert response.data["company_name"] == "Company B"

    def test_create_job_posting(self):
        """채용 공고 생성"""
        # Given
        data = {
            "posting_id": 3,
            "url": "https://example.com/job/3",
            "company_name": "Company C",
            "position": "Data Engineer",
            "main_tasks": "Data pipeline",
            "requirements": "Python, Spark",
            "preferred_points": "Airflow",
            "location": "Seoul",
            "district": "Gangnam",
            "employment_type": "Full-time",
            "career_min": 3,
            "career_max": 7,
        }

        # When
        response = self.client.post("/api/v1/jobs/", data, format="json")

        # Then
        assert response.status_code == status.HTTP_201_CREATED
        assert JobPosting.objects.filter(posting_id=3).exists()

    def test_update_job_posting(self):
        """채용 공고 수정"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=4,
            url="https://example.com/job/4",
            company_name="Old Company",
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

        data = {"company_name": "New Company"}

        # When
        response = self.client.patch(
            f"/api/v1/jobs/{posting.posting_id}/", data, format="json"
        )

        # Then
        assert response.status_code == status.HTTP_200_OK
        posting.refresh_from_db()
        assert posting.company_name == "New Company"

    def test_delete_job_posting(self):
        """채용 공고 삭제"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=5,
            url="https://example.com/job/5",
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

        # When
        response = self.client.delete(f"/api/v1/jobs/{posting.posting_id}/")

        # Then
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not JobPosting.objects.filter(posting_id=5).exists()

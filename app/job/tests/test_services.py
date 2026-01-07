"""
Tests for JobService

JobPosting 비즈니스 로직 테스트
"""

from unittest.mock import MagicMock, patch

import pytest
from job.models import JobPosting
from job.services import JobService


@pytest.mark.django_db
class TestJobService:
    """JobService 단위 테스트"""

    def test_get_job_posting_success(self):
        """채용 공고 조회 성공"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=1,
            url="https://example.com/job/1",
            company_name="Test Company",
            position="Backend Developer",
            main_tasks="Development",
            requirements="Python, Django",
            preferred_points="AWS",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=5,
        )

        # When
        result = JobService.get_job_posting(1)

        # Then
        assert result is not None
        assert result.posting_id == 1
        assert result.company_name == "Test Company"

    def test_get_job_posting_not_found(self):
        """존재하지 않는 채용 공고 조회"""
        # When
        result = JobService.get_job_posting(9999)

        # Then
        assert result is None

    def test_create_job_posting(self):
        """채용 공고 생성"""
        # Given
        data = {
            "posting_id": 2,
            "url": "https://example.com/job/2",
            "company_name": "New Company",
            "position": "Frontend Developer",
            "main_tasks": "React Development",
            "requirements": "React, TypeScript",
            "preferred_points": "Next.js",
            "location": "Seoul",
            "district": "Gangnam",
            "employment_type": "Full-time",
            "career_min": 2,
            "career_max": 4,
        }

        # When
        posting = JobService.create_job_posting(data)

        # Then
        assert posting.posting_id == 2
        assert posting.company_name == "New Company"
        assert JobPosting.objects.filter(posting_id=2).exists()

    def test_update_job_posting(self):
        """채용 공고 수정"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=3,
            url="https://example.com/job/3",
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

        # When
        updated = JobService.update_job_posting(3, {"company_name": "New Company"})

        # Then
        assert updated is not None
        assert updated.company_name == "New Company"

    def test_delete_job_posting(self):
        """채용 공고 삭제"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=4,
            url="https://example.com/job/4",
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
        result = JobService.delete_job_posting(4)

        # Then
        assert result is True
        assert not JobPosting.objects.filter(posting_id=4).exists()

    @patch("job.services.Neo4jGraphStore")
    @patch("job.services.ChromaVectorStore")
    @patch("job.application.usecases.process_job_posting.SkillExtractionService")
    def test_process_job_posting_sync_success(
        self, mock_skill_service, mock_vector_store, mock_graph_store
    ):
        """채용 공고 처리 (동기) 성공"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=5,
            url="https://example.com/job/5",
            company_name="Test Company",
            position="Backend Developer",
            main_tasks="Python development",
            requirements="Python, Django required",
            preferred_points="AWS preferred",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=5,
        )

        # Mock skill extraction
        mock_skill_service.extract_skills_from_job_posting.return_value = (
            ["Python", "Django"],
            "AWS preferred",
        )

        # Mock vector/graph
        mock_vector_store.return_value.upsert_text.return_value = None
        mock_graph_store.return_value.upsert_job_posting.return_value = None

        # When
        result = JobService.process_job_posting_sync(5)

        # Then
        assert result["success"] is True
        assert result["posting_id"] == 5
        assert result["skills_required"] == 2

        # Verify DB was updated
        posting.refresh_from_db()
        assert posting.skills_required == ["Python", "Django"]

    def test_process_job_posting_sync_not_found(self):
        """존재하지 않는 채용 공고 처리"""
        # When
        result = JobService.process_job_posting_sync(9999)

        # Then
        assert result["success"] is False
        assert "not found" in result["error"]

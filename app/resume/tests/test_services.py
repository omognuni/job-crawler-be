"""
Tests for ResumeService

이력서 비즈니스 로직 테스트
"""

from unittest.mock import MagicMock, patch

import pytest
from resume.models import Resume
from resume.services import ResumeService


@pytest.mark.django_db
class TestResumeService:
    """ResumeService 단위 테스트"""

    def test_get_resume_success(self):
        """이력서 조회 성공"""
        # Given
        resume = Resume.objects.create(
            user_id=1,
            content="Backend Developer with 5 years of experience in Python and Django.",
        )

        # When
        result = ResumeService.get_resume(1)

        # Then
        assert result is not None
        assert result.user_id == 1

    def test_get_resume_not_found(self):
        """존재하지 않는 이력서 조회"""
        # When
        result = ResumeService.get_resume(9999)

        # Then
        assert result is None

    def test_create_resume(self):
        """이력서 생성"""
        # Given
        data = {
            "user_id": 2,
            "content": "Frontend Developer with React experience.",
        }

        # When
        resume = ResumeService.create_resume(data)

        # Then
        assert resume.user_id == 2
        assert Resume.objects.filter(user_id=2).exists()

    def test_update_resume(self):
        """이력서 수정"""
        # Given
        resume = Resume.objects.create(
            user_id=3,
            content="Old content",
        )

        # When
        updated = ResumeService.update_resume(3, {"content": "New content"})

        # Then
        assert updated is not None
        assert updated.content == "New content"

    def test_delete_resume(self):
        """이력서 삭제"""
        # Given
        resume = Resume.objects.create(
            user_id=4,
            content="Content to delete",
        )

        # When
        result = ResumeService.delete_resume(4)

        # Then
        assert result is True
        assert not Resume.objects.filter(user_id=4).exists()

    @patch("resume.services.os.getenv")
    @patch("resume.services.SkillExtractionService")
    def test_analyze_resume_with_llm_no_api_key(self, mock_skill_service, mock_getenv):
        """API 키 없이 이력서 분석 (Fallback)"""
        # Given
        mock_getenv.return_value = None
        mock_skill_service.extract_skills.return_value = ["Python", "Django"]

        content = "Backend Developer with Python and Django experience"

        # When
        result = ResumeService.analyze_resume_with_llm(content)

        # Then
        assert result["skills"] == ["Python", "Django"]
        assert result["career_years"] == 0
        assert "API 키" in result["strengths"]

    @patch("resume.services.vector_db_client")
    @patch("resume.services.SkillExtractionService")
    @patch("resume.services.os.getenv")
    def test_process_resume_sync_success(
        self, mock_getenv, mock_skill_service, mock_vector_db
    ):
        """이력서 처리 (동기) 성공"""
        # Given
        resume = Resume.objects.create(
            user_id=5,
            content="Backend Developer with 5 years in Python",
        )

        mock_getenv.return_value = None  # Fallback mode
        mock_skill_service.extract_skills.return_value = ["Python", "Django"]

        # Mock vector DB
        mock_collection = MagicMock()
        mock_vector_db.get_or_create_collection.return_value = mock_collection

        # When
        result = ResumeService.process_resume_sync(5)

        # Then
        assert result["success"] is True
        assert result["user_id"] == 5
        assert result["skills_count"] == 2

        # Verify DB was updated
        resume.refresh_from_db()
        assert resume.analysis_result is not None
        assert "skills" in resume.analysis_result

    @patch("resume.services.SkillExtractionService")
    def test_process_resume_sync_not_found(self, mock_skill_service):
        """존재하지 않는 이력서 처리"""
        # When
        result = ResumeService.process_resume_sync(9999)

        # Then
        assert result["success"] is False
        assert "not found" in result["error"]

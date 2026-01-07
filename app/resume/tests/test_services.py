"""
Tests for ResumeService

이력서 비즈니스 로직 테스트
"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from resume.models import Resume
from resume.services import ResumeService

User = get_user_model()


@pytest.mark.django_db
class TestResumeService:
    """ResumeService 단위 테스트"""

    def test_get_resume_success(self):
        """이력서 조회 성공"""
        # Given
        user = User.objects.create_user(username="testuser1", password="password")
        resume = Resume.objects.create(
            user=user,
            title="My Resume",
            content="Backend Developer with 5 years of experience in Python and Django.",
        )

        # When
        result = ResumeService.get_resume(user.id)

        # Then
        assert result is not None
        assert result.user_id == user.id
        assert result.id == resume.id

    def test_get_resume_not_found(self):
        """존재하지 않는 이력서 조회"""
        # When
        result = ResumeService.get_resume(9999)

        # Then
        assert result is None

    def test_create_resume(self):
        """이력서 생성"""
        # Given
        user = User.objects.create_user(username="testuser2", password="password")
        data = {
            "user": user,
            "title": "New Resume",
            "content": "Frontend Developer with React experience.",
        }

        # When
        resume = ResumeService.create_resume(data)

        # Then
        assert resume.user_id == user.id
        assert Resume.objects.filter(user=user).exists()

    def test_update_resume(self):
        """이력서 수정"""
        # Given
        user = User.objects.create_user(username="testuser3", password="password")
        resume = Resume.objects.create(
            user=user,
            content="Old content",
        )

        # When
        updated = ResumeService.update_resume(
            resume.id, user.id, {"content": "New content"}
        )

        # Then
        assert updated is not None
        assert updated.content == "New content"

    def test_delete_resume(self):
        """이력서 삭제"""
        # Given
        user = User.objects.create_user(username="testuser4", password="password")
        resume = Resume.objects.create(
            user=user,
            content="Content to delete",
        )

        # When
        result = ResumeService.delete_resume(resume.id, user.id)

        # Then
        assert result is True
        assert not Resume.objects.filter(id=resume.id).exists()

    @patch("common.adapters.google_genai_resume_analyzer.os.getenv")
    @patch("resume.services.SkillExtractionService")
    def test_analyze_resume_with_llm_no_api_key(self, mock_skill_service, mock_getenv):
        """API 키 없이 이력서 분석 (Fallback)"""
        # Given
        mock_getenv.return_value = None
        mock_skill_service.extract_skills.return_value = ["Python", "Django"]

        content = "Backend Developer with Python and Django experience"

        # When
        result = ResumeService._analyze_resume_with_llm(content)

        # Then
        assert result.skills == ["Python", "Django"]
        assert result.position == "백엔드 개발자"
        assert result.career_years == 0
        assert "API 키" in result.strengths

    @patch("resume.services.ChromaVectorStore")
    @patch("resume.application.usecases.process_resume.SkillExtractionService")
    @patch("common.adapters.google_genai_resume_analyzer.os.getenv")
    def test_process_resume_sync_success(
        self, mock_getenv, mock_skill_service, mock_vector_store
    ):
        """이력서 처리 (동기) 성공"""
        # Given
        user = User.objects.create_user(username="testuser5", password="password")
        resume = Resume.objects.create(
            user=user,
            content="Backend Developer with 5 years in Python",
        )

        mock_getenv.return_value = None  # Fallback mode
        mock_skill_service.extract_skills.return_value = ["Python", "Django"]

        # Mock vector store
        mock_vector_store.return_value.upsert_text.return_value = None

        # When
        result = ResumeService.process_resume_sync(resume.id)

        # Then
        assert result.success is True
        assert result.resume_id == resume.id
        assert result.user_id == user.id
        assert result.skills_count == 2

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
        assert result.success is False
        assert "not found" in result.error

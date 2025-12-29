"""
Tests for RecommendationService

추천 시스템 비즈니스 로직 테스트
"""

from unittest.mock import MagicMock, patch

import pytest
from job.models import JobPosting
from recommendation.models import JobRecommendation
from recommendation.services import RecommendationService
from resume.models import Resume


@pytest.mark.django_db
class TestRecommendationService:
    """RecommendationService 단위 테스트"""

    def test_calculate_match_score_perfect_match(self):
        """완벽한 매칭 점수 계산"""
        # Given
        posting = JobPosting(
            posting_id=1,
            company_name="Test Company",
            position="Backend Developer",
            url="https://example.com/job/1",
            main_tasks="Development",
            requirements="Python, Django",
            preferred_points="AWS, Docker",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=5,
            skills_required=["Python", "Django", "PostgreSQL"],
            skills_preferred="AWS, Docker",
        )

        user_skills = {"Python", "Django", "PostgreSQL", "AWS", "Docker"}
        user_career_years = 4

        # When
        score, reason = RecommendationService._calculate_match_score_and_reason(
            posting, user_skills, user_career_years
        )

        # Then
        assert score == 100  # Perfect match
        assert "필수 스킬" in reason
        assert "경력 요건 충족" in reason

    def test_calculate_match_score_partial_match(self):
        """부분 매칭 점수 계산"""
        # Given
        posting = JobPosting(
            posting_id=2,
            company_name="Test Company",
            position="Backend Developer",
            url="https://example.com/job/2",
            main_tasks="Development",
            requirements="Python, Django",
            preferred_points="AWS",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=5,
            skills_required=["Python", "Django", "PostgreSQL"],
            skills_preferred="AWS",
        )

        user_skills = {"Python", "Django"}  # Missing PostgreSQL
        user_career_years = 2  # Below minimum

        # When
        score, reason = RecommendationService._calculate_match_score_and_reason(
            posting, user_skills, user_career_years
        )

        # Then
        assert 0 < score < 100
        assert "필수 스킬" in reason

    @patch("recommendation.services.vector_db_client")
    @patch("recommendation.services.graph_db_client")
    def test_get_recommendations_success(self, mock_graph_db, mock_vector_db):
        """추천 생성 성공"""
        # Given
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="password")
        resume = Resume.objects.create(
            user_id=user.id,
            content="Backend Developer",
            analysis_result={
                "skills": ["Python", "Django"],
                "career_years": 3,
            },
        )

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
            career_min=2,
            career_max=5,
            skills_required=["Python", "Django"],
        )

        # Mock ChromaDB
        mock_resumes_collection = MagicMock()
        mock_jobs_collection = MagicMock()

        mock_vector_db.get_or_create_collection.side_effect = [
            mock_resumes_collection,
            mock_jobs_collection,
        ]

        mock_resumes_collection.get.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}

        mock_jobs_collection.query.return_value = {"ids": [["1"]]}

        # Mock Neo4j
        # 1. _get_postings_by_skills 호출 결과
        # 2. _filter_by_skill_graph 내부 호출 결과 (posting_id=1)
        mock_graph_db.execute_query.side_effect = [
            [{"posting_id": 1}],  # _get_postings_by_skills
            [
                {"skill_name": "Python"},
                {"skill_name": "Django"},
            ],  # _filter_by_skill_graph
        ]

        # When
        recommendations = RecommendationService.get_recommendations(resume.id, limit=10)

        # Then
        assert len(recommendations) > 0
        assert recommendations[0]["posting_id"] == 1

    def test_filter_by_skill_graph_empty_skills(self):
        """스킬이 없는 경우 필터링"""
        # Given
        posting_ids = [1, 2, 3]
        user_skills = set()

        # When
        result = RecommendationService._filter_by_skill_graph(posting_ids, user_skills)

        # Then
        assert result == posting_ids  # 스킬이 없으면 필터링 안함

    def test_get_recommendation_success(self):
        """추천 조회 성공"""
        # Given
        posting = JobPosting.objects.create(
            posting_id=10,
            url="https://example.com/job/10",
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
            user_id=1,
            job_posting=posting,
            rank=1,
            match_score=85.0,
            match_reason="Great match",
        )

        # When
        result = RecommendationService.get_recommendation(recommendation.id)

        # Then
        assert result is not None
        assert result.user_id == 1

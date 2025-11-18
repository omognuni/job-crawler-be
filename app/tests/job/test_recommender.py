"""
Tests for AI-Free recommendation engine.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from job.models import JobPosting, Resume
from job.recommender import (
    _calculate_match_score_and_reason,
    _filter_by_skill_graph,
    get_recommendations,
    get_skill_statistics,
)


@pytest.mark.django_db
class TestRecommenderEngine:
    """Tests for recommendation engine"""

    def test_calculate_match_score_with_perfect_match(self):
        """
        모든 스킬과 경력이 완벽하게 일치하는 경우
        """
        posting = JobPosting(
            posting_id=1,
            company_name="Test Company",
            position="Backend Developer",
            url="https://example.com/job/1",
            main_tasks="Development",
            requirements="Required",
            preferred_points="Preferred",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=5,
            skills_required=["Python", "Django", "PostgreSQL"],
            skills_preferred=["AWS", "Docker"],
        )

        user_skills = {"Python", "Django", "PostgreSQL", "AWS", "Docker"}
        user_career_years = 4

        score, reason = _calculate_match_score_and_reason(
            posting, user_skills, user_career_years
        )

        # 필수(50) + 우대(30) + 경력(20) = 100
        assert score == 100
        assert "필수 스킬" in reason
        assert "우대 스킬" in reason
        assert "경력 요건 충족" in reason

    def test_calculate_match_score_with_partial_match(self):
        """
        일부 스킬만 일치하는 경우
        """
        posting = JobPosting(
            posting_id=1,
            company_name="Test Company",
            position="Backend Developer",
            url="https://example.com/job/1",
            main_tasks="Development",
            requirements="Required",
            preferred_points="Preferred",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=5,
            skills_required=["Python", "Django", "PostgreSQL", "Redis"],
            skills_preferred=["AWS", "Docker"],
        )

        # 4개 필수 스킬 중 2개만 보유
        user_skills = {"Python", "Django"}
        user_career_years = 4

        score, reason = _calculate_match_score_and_reason(
            posting, user_skills, user_career_years
        )

        # 필수(25) + 우대(0) + 경력(20) = 45
        assert score == 45
        assert "일부 보유" in reason or "필수 스킬" in reason

    def test_calculate_match_score_with_no_skills(self):
        """
        스킬 매칭이 전혀 없는 경우
        """
        posting = JobPosting(
            posting_id=1,
            company_name="Test Company",
            position="Backend Developer",
            url="https://example.com/job/1",
            main_tasks="Development",
            requirements="Required",
            preferred_points="Preferred",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=5,
            skills_required=["Java", "Spring"],
            skills_preferred=[],
        )

        user_skills = {"Python", "Django"}
        user_career_years = 4

        score, reason = _calculate_match_score_and_reason(
            posting, user_skills, user_career_years
        )

        # 경력만 일치(20)
        assert score == 20
        assert "경력 요건 충족" in reason

    def test_calculate_match_score_career_mismatch(self):
        """
        경력 범위가 맞지 않는 경우
        """
        posting = JobPosting(
            posting_id=1,
            company_name="Test Company",
            position="Senior Backend Developer",
            url="https://example.com/job/1",
            main_tasks="Development",
            requirements="Required",
            preferred_points="Preferred",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=5,
            career_max=10,
            skills_required=["Python"],
            skills_preferred=[],
        )

        user_skills = {"Python"}
        user_career_years = 2  # 너무 적음

        score, reason = _calculate_match_score_and_reason(
            posting, user_skills, user_career_years
        )

        # 필수 스킬(50)만
        assert score == 50
        assert "경력" not in reason or "근접" not in reason

    @patch("job.recommender.graph_db_client")
    def test_filter_by_skill_graph(self, mock_graph):
        """
        Neo4j 스킬 그래프 필터링 테스트
        """
        # Mock Neo4j query results
        mock_graph.execute_query.side_effect = [
            # Posting 1: Python, Django 스킬 보유
            [
                {"skill_name": "Python", "skill_type": "required"},
                {"skill_name": "Django", "skill_type": "required"},
            ],
            # Posting 2: Python 스킬만 보유
            [
                {"skill_name": "Python", "skill_type": "required"},
            ],
            # Posting 3: Java 스킬 보유 (매칭 안됨)
            [
                {"skill_name": "Java", "skill_type": "required"},
            ],
        ]

        posting_ids = [1, 2, 3]
        user_skills = {"Python", "Django"}

        result = _filter_by_skill_graph(posting_ids, user_skills)

        # Posting 1이 2개 매칭으로 1위, Posting 2가 1개 매칭으로 2위
        # Posting 3은 매칭 없어서 제외
        assert result == [1, 2]
        assert mock_graph.execute_query.call_count == 3

    @patch("job.recommender.graph_db_client")
    @patch("job.recommender.vector_db_client")
    def test_get_recommendations_success(self, mock_vector_db, mock_graph):
        """
        추천 엔진 전체 플로우 성공 테스트
        """
        # Create test resume
        resume = Resume.objects.create(
            user_id=101,
            content="Python Django developer with 3 years experience",
            analysis_result={
                "skills": ["Python", "Django", "PostgreSQL"],
                "career_years": 3,
            },
        )

        # Create test job postings
        JobPosting.objects.create(
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
            career_max=4,
            skills_required=["Python", "Django"],
            skills_preferred=["PostgreSQL"],
        )

        JobPosting.objects.create(
            posting_id=2,
            company_name="Company B",
            position="Full Stack Developer",
            url="https://example.com/job/2",
            main_tasks="Development",
            requirements="Required",
            preferred_points="Preferred",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=5,
            skills_required=["Python"],
            skills_preferred=["Django"],
        )

        # Mock vector DB responses
        mock_resumes_collection = Mock()
        mock_job_postings_collection = Mock()
        mock_vector_db.get_or_create_collection.side_effect = [
            mock_resumes_collection,
            mock_job_postings_collection,
        ]

        # Mock resume vector retrieval
        mock_resumes_collection.get.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}

        # Mock similar job postings query
        mock_job_postings_collection.query.return_value = {
            "ids": [["1", "2"]],
        }

        # Mock Neo4j skill matching
        mock_graph.execute_query.side_effect = [
            [
                {"skill_name": "Python", "skill_type": "required"},
                {"skill_name": "Django", "skill_type": "required"},
            ],
            [
                {"skill_name": "Python", "skill_type": "required"},
            ],
        ]

        # Get recommendations
        recommendations = get_recommendations(user_id=101, limit=10)

        # Verify results
        assert len(recommendations) == 2
        assert recommendations[0]["posting_id"] == 1  # Better match should be first
        assert recommendations[0]["match_score"] == 100
        assert recommendations[1]["posting_id"] == 2
        assert "match_reason" in recommendations[0]
        assert "company_name" in recommendations[0]
        assert "position" in recommendations[0]

    @patch("job.recommender.vector_db_client")
    def test_get_recommendations_no_resume(self, mock_vector_db):
        """
        이력서가 없는 경우 빈 리스트 반환
        """
        recommendations = get_recommendations(user_id=999, limit=10)
        assert recommendations == []

    @patch("job.recommender.vector_db_client")
    def test_get_recommendations_no_skills(self, mock_vector_db):
        """
        스킬이 없는 경우 빈 리스트 반환
        """
        Resume.objects.create(
            user_id=102,
            content="New graduate",
            analysis_result={
                "skills": [],
                "career_years": 0,
            },
        )

        recommendations = get_recommendations(user_id=102, limit=10)
        assert recommendations == []

    @patch("job.recommender.graph_db_client")
    @patch("job.recommender.vector_db_client")
    def test_get_recommendations_no_vector(self, mock_vector_db, mock_graph):
        """
        벡터 임베딩이 없는 경우 빈 리스트 반환
        """
        Resume.objects.create(
            user_id=103,
            content="Python developer",
            analysis_result={
                "skills": ["Python"],
                "career_years": 2,
            },
        )

        mock_resumes_collection = Mock()
        mock_vector_db.get_or_create_collection.return_value = mock_resumes_collection

        # No embedding found
        mock_resumes_collection.get.return_value = {"embeddings": None}

        recommendations = get_recommendations(user_id=103, limit=10)
        assert recommendations == []

    @patch("job.recommender.graph_db_client")
    def test_get_skill_statistics(self, mock_graph):
        """
        스킬 통계 조회 테스트
        """
        mock_graph.get_skill_statistics.return_value = {
            "skill_name": "Python",
            "required_count": 50,
            "preferred_count": 30,
            "total_count": 80,
        }

        stats = get_skill_statistics("Python")

        assert stats["skill_name"] == "Python"
        assert stats["total_count"] == 80
        mock_graph.get_skill_statistics.assert_called_once_with("Python")

    def test_match_score_max_100(self):
        """
        Match score가 100을 초과하지 않는지 확인
        """
        posting = JobPosting(
            posting_id=1,
            company_name="Test Company",
            position="Backend Developer",
            url="https://example.com/job/1",
            main_tasks="Development",
            requirements="Required",
            preferred_points="Preferred",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=5,
            skills_required=["Python"],
            skills_preferred=["Django"],
        )

        user_skills = {"Python", "Django", "JavaScript", "React", "AWS"}
        user_career_years = 4

        score, reason = _calculate_match_score_and_reason(
            posting, user_skills, user_career_years
        )

        assert score <= 100

    def test_filter_by_skill_graph_empty_skills(self):
        """
        사용자 스킬이 없으면 원본 리스트 반환
        """
        posting_ids = [1, 2, 3]
        user_skills = set()

        result = _filter_by_skill_graph(posting_ids, user_skills)

        assert result == posting_ids

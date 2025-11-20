"""
Performance Tests for Recommendation System

추천 시스템 성능 테스트
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from job.models import JobPosting
from recommendation.services import RecommendationService
from resume.models import Resume


@pytest.mark.django_db
class TestRecommendationPerformance:
    """추천 시스템 성능 테스트"""

    @patch("recommendation.services.vector_db_client")
    @patch("recommendation.services.graph_db_client")
    def test_recommendation_response_time(self, mock_graph_db, mock_vector_db):
        """추천 시스템 응답 시간 측정 (목표: < 500ms)"""
        # Given
        resume = Resume.objects.create(
            user_id=1,
            content="Backend Developer with Python and Django experience",
            analysis_result={
                "skills": ["Python", "Django", "PostgreSQL"],
                "career_years": 3,
            },
        )

        # Create multiple job postings
        for i in range(1, 21):
            JobPosting.objects.create(
                posting_id=i,
                url=f"https://example.com/job/{i}",
                company_name=f"Company {i}",
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

        mock_resumes_collection.get.return_value = {
            "embeddings": [[0.1] * 384]  # Simulate embedding
        }

        mock_jobs_collection.query.return_value = {
            "ids": [[str(i) for i in range(1, 21)]]
        }

        # Mock Neo4j
        mock_graph_db.execute_query.return_value = [
            {"skill_name": "Python"},
            {"skill_name": "Django"},
        ]

        # When
        start_time = time.time()
        recommendations = RecommendationService.get_recommendations(1, limit=10)
        elapsed_time = time.time() - start_time

        # Then
        assert len(recommendations) > 0
        assert elapsed_time < 0.5, f"Response time {elapsed_time:.3f}s exceeds 500ms"
        print(f"\n✓ Recommendation response time: {elapsed_time:.3f}s")

    def test_skill_extraction_performance(self):
        """스킬 추출 성능 테스트"""
        from skill.services import SkillExtractionService

        # Given
        long_text = (
            """
        We are looking for a talented developer with experience in:
        Python, Django, Flask, FastAPI, PostgreSQL, MySQL, MongoDB, Redis,
        Docker, Kubernetes, AWS, GCP, Azure, Git, GitHub, GitLab,
        React, Vue.js, Angular, TypeScript, JavaScript, HTML, CSS,
        Nginx, Apache, Linux, Unix, Kafka, RabbitMQ, Elasticsearch
        """
            * 10
        )  # Repeat to make it longer

        # When
        start_time = time.time()
        skills = SkillExtractionService.extract_skills(long_text)
        elapsed_time = time.time() - start_time

        # Then
        assert len(skills) > 10
        assert (
            elapsed_time < 0.1
        ), f"Skill extraction time {elapsed_time:.3f}s exceeds 100ms"
        print(f"\n✓ Skill extraction time: {elapsed_time:.3f}s")
        print(f"  Extracted {len(skills)} skills from {len(long_text)} characters")

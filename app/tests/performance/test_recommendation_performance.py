"""
Performance Tests for Recommendation System

추천 시스템 성능 테스트
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from job.models import JobPosting
from recommendation.services import RecommendationService
from resume.models import Resume

User = get_user_model()


@pytest.mark.django_db
class TestRecommendationPerformance:
    """추천 시스템 성능 테스트"""

    @patch("recommendation.services.vector_store")
    @patch("recommendation.services.graph_store")
    def test_recommendation_response_time(self, mock_graph_store, mock_vector_store):
        """추천 시스템 응답 시간 측정 (목표: < 500ms)"""
        # Given
        user = User.objects.create_user(username="perfuser", password="password")
        resume = Resume.objects.create(
            user=user,
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
        mock_vector_store.get_embedding.return_value = [0.1] * 384
        mock_vector_store.query_by_embedding.return_value = {
            "ids": [[str(i) for i in range(1, 21)]],
            "distances": [[0.2 for _ in range(1, 21)]],
        }

        # Mock Neo4j
        mock_graph_store.get_postings_by_skills.return_value = list(range(1, 21))
        mock_graph_store.get_required_skills.return_value = {"Python", "Django"}

        # When
        start_time = time.time()
        recommendations = RecommendationService.get_recommendations(resume.id, limit=10)
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

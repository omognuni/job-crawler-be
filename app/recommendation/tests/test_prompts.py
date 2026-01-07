import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from job.models import JobPosting
from recommendation.models import RecommendationPrompt
from rest_framework.test import APIClient
from resume.models import Resume

User = get_user_model()


@pytest.mark.django_db
class TestRecommendationPrompt:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.user_id = self.user.id
        self.resume = Resume.objects.create(
            user=self.user,
            content="Python Django Developer with 5 years of experience.",
            analysis_result={"skills": ["Python", "Django"], "career_years": 5},
            experience_summary="Experienced Python Developer",
        )
        self.job_posting = JobPosting.objects.create(
            posting_id=1,
            url="http://example.com",
            company_name="Test Corp",
            position="Python Dev",
            main_tasks="Develop backend",
            requirements="Python, Django",
            preferred_points="AWS",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=3,
            career_max=7,
            skills_required=["Python", "Django"],
        )
        self.prompt = RecommendationPrompt.objects.create(
            name="Strict Recruiter",
            content="You are a strict recruiter. Be critical.",
            is_active=True,
        )

    def test_list_prompts(self):
        """프롬프트 목록 조회 테스트"""
        self.client.force_authenticate(user=self.user)

        url = reverse("recommendation-prompt-list")
        response = self.client.get(url)

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["name"] == "Strict Recruiter"

    def test_recommendation_with_prompt(self):
        """프롬프트 적용 추천 테스트 (Mock LLM)"""
        from unittest.mock import patch

        self.client.force_authenticate(user=self.user)

        # Mock RecommendationService._evaluate_match_batch_with_llm (외부 LLM 호출 방지)
        with patch(
            "recommendation.services.RecommendationService._evaluate_match_batch_with_llm"
        ) as mock_llm:
            mock_llm.return_value = [
                {"score": 85, "reason": "Critical evaluation result"}
            ]

            # Mock vector/graph search to return our job posting
            with (
                patch("recommendation.services.vector_store") as mock_vector_store,
                patch("recommendation.services.graph_store") as mock_graph_store,
            ):
                mock_vector_store.get_embedding.return_value = [0.1] * 10
                mock_vector_store.query_by_embedding.return_value = {
                    "ids": [[str(self.job_posting.posting_id)]],
                    "distances": [[0.2]],
                }
                mock_graph_store.get_postings_by_skills.return_value = [
                    self.job_posting.posting_id
                ]
                mock_graph_store.get_required_skills.return_value = {"Python", "Django"}

                url = reverse(
                    "recommendation-for-resume", kwargs={"resume_id": self.resume.id}
                )
                response = self.client.get(url, {"prompt_id": self.prompt.id})

                assert response.status_code == 200
                assert len(response.data) > 0
                assert response.data[0]["match_score"] == 85
                assert response.data[0]["match_reason"] == "Critical evaluation result"

                # Verify LLM was called with correct prompt
                mock_llm.assert_called_once()
                args, _ = mock_llm.call_args
                assert args[2].id == self.prompt.id

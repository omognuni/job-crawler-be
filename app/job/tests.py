import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.test import Client, TestCase
from job.models import JobPosting
from skill.services import MASTER_SKILLS, extract_skills


def create_test_job_posting(**kwargs):
    """테스트용 JobPosting 객체를 생성하는 헬퍼 함수"""
    defaults = {
        "url": "http://example.com",
        "main_tasks": "",
        "requirements": "",
        "preferred_points": "",
        "location": "",
        "district": "",
        "employment_type": "",
        "career_min": 0,
        "career_max": 0,
    }
    defaults.update(kwargs)
    return JobPosting.objects.create(**defaults)


class TestSkillExtraction(TestCase):
    """스킬 추출 함수 테스트"""

    def test_extract_skills_backend(self):
        """백엔드 기술 스택 추출 테스트"""
        text = "Python, Django, FastAPI를 사용하여 백엔드 개발"
        skills = extract_skills(text)

        self.assertIn("Python", skills)
        self.assertIn("Django", skills)
        self.assertIn("FastAPI", skills)

    def test_extract_skills_frontend(self):
        """프론트엔드 기술 스택 추출 테스트"""
        text = "React, TypeScript, Next.js 경험"
        skills = extract_skills(text)

        self.assertIn("React", skills)
        self.assertIn("TypeScript", skills)
        self.assertIn("Next.js", skills)

    def test_extract_skills_database(self):
        """데이터베이스 기술 추출 테스트"""
        text = "PostgreSQL, MongoDB, Redis 사용 경험"
        skills = extract_skills(text)

        self.assertIn("PostgreSQL", skills)
        self.assertIn("MongoDB", skills)
        self.assertIn("Redis", skills)

    def test_extract_skills_case_insensitive(self):
        """대소문자 무관 추출 테스트"""
        text = "python, DJANGO, fastapi"
        skills = extract_skills(text)

        self.assertIn("Python", skills)
        self.assertIn("Django", skills)
        self.assertIn("FastAPI", skills)

    def test_extract_skills_empty_text(self):
        """빈 텍스트 테스트"""
        skills = extract_skills("")
        self.assertEqual(skills, [])

    def test_master_skills_count(self):
        """마스터 스킬 목록 개수 확인"""
        self.assertGreater(len(MASTER_SKILLS), 50)


@pytest.mark.django_db
class TestJobPostingModel(TestCase):
    @patch("job.tasks.process_job_posting.delay")
    def test_job_posting_schedules_celery_task_on_save(self, mock_task_delay):
        """
        JobPosting 저장 시 Celery 태스크가 스케줄링되는지 테스트
        """
        # JobPosting 생성
        job_posting = create_test_job_posting(
            posting_id=123,
            company_name="Test Corp",
            position="Software Engineer",
            main_tasks="Develop amazing things with Python.",
            requirements="Python, Django",
            preferred_points="FastAPI, AWS",
            career_min=1,
            career_max=5,
        )

        # Celery 태스크가 호출되었는지 확인
        mock_task_delay.assert_called_once_with(123)


@pytest.mark.django_db
class TestJobPostingCRUD(TestCase):
    """JobPosting CRUD 테스트"""

    def test_create_job_posting(self):
        """JobPosting 생성 테스트"""
        posting = create_test_job_posting(
            posting_id=101, company_name="Test Corp", position="Backend Developer"
        )

        self.assertEqual(posting.posting_id, 101)
        self.assertEqual(posting.company_name, "Test Corp")
        self.assertEqual(posting.position, "Backend Developer")

    def test_job_posting_str(self):
        """JobPosting __str__ 메서드 테스트"""
        posting = create_test_job_posting(
            posting_id=101,
            company_name="Test Corp",
            position="Backend Developer",
            url="http://example.com/job/101",
        )

        expected_str = "Test Corp - Backend Developer - http://example.com/job/101"
        self.assertEqual(str(posting), expected_str)


@pytest.mark.django_db
class TestJobViews(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("job.views.graph_db_client")
    def test_related_jobs_view(self, mock_graph_client):
        """
        RelatedJobsView가 스킬 기반으로 관계 추천 결과를 반환하는지 테스트
        """
        # 테스트 데이터 생성
        create_test_job_posting(
            posting_id=201, position="Backend Dev", company_name="RelateCorp"
        )
        create_test_job_posting(
            posting_id=202, position="Frontend Dev", company_name="RelateCorp"
        )

        # Mock setup
        mock_graph_client.get_jobs_related_to_skill.return_value = [201, 202]

        # API 호출
        response = self.client.get("/api/v1/related-by-skill/Python/")

        # Assertions
        self.assertEqual(response.status_code, 200)
        mock_graph_client.get_jobs_related_to_skill.assert_called_once_with("Python")

        response_data = response.json()
        self.assertEqual(len(response_data), 2)
        self.assertSetEqual({item["posting_id"] for item in response_data}, {201, 202})

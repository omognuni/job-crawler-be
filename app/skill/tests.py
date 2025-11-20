"""
Skill App Tests

스킬 추출 및 API 테스트
"""

from unittest.mock import patch

import pytest
from django.test import Client, TestCase
from job.models import JobPosting
from skill.services import (
    MASTER_SKILLS,
    SkillExtractionService,
    extract_skills,
    extract_skills_from_job_posting,
    get_all_skills,
    get_skill_count,
)


class TestSkillExtractionService(TestCase):
    """SkillExtractionService 클래스 테스트"""

    def test_extract_skills_backend(self):
        """백엔드 기술 스택 추출"""
        text = "Python, Django, FastAPI를 사용하여 백엔드 개발"
        skills = SkillExtractionService.extract_skills(text)

        self.assertIn("Python", skills)
        self.assertIn("Django", skills)
        self.assertIn("FastAPI", skills)

    def test_extract_skills_frontend(self):
        """프론트엔드 기술 스택 추출"""
        text = "React, TypeScript, Next.js 경험"
        skills = SkillExtractionService.extract_skills(text)

        self.assertIn("React", skills)
        self.assertIn("TypeScript", skills)
        self.assertIn("Next.js", skills)

    def test_extract_skills_empty_text(self):
        """빈 텍스트 처리"""
        self.assertEqual(SkillExtractionService.extract_skills(""), [])
        self.assertEqual(SkillExtractionService.extract_skills(None), [])

    def test_extract_skills_case_insensitive(self):
        """대소문자 무관"""
        text = "python DJANGO fastapi"
        skills = SkillExtractionService.extract_skills(text)

        self.assertIn("Python", skills)
        self.assertIn("Django", skills)
        self.assertIn("FastAPI", skills)

    def test_extract_skills_from_job_posting(self):
        """채용공고용 스킬 추출"""
        requirements = "Python, Django 경험 필수"
        preferred = "AWS, Docker 경험자 우대"

        required, preferred_text = (
            SkillExtractionService.extract_skills_from_job_posting(
                requirements, preferred
            )
        )

        self.assertIn("Python", required)
        self.assertIn("Django", required)
        self.assertIn("AWS", preferred_text)
        self.assertIn("Docker", preferred_text)

    def test_get_all_skills(self):
        """전체 스킬 목록 조회"""
        all_skills = SkillExtractionService.get_all_skills()

        self.assertIsInstance(all_skills, list)
        self.assertGreater(len(all_skills), 50)
        self.assertIn("Python", all_skills)
        self.assertEqual(all_skills, sorted(all_skills))

    def test_get_skill_count(self):
        """스킬 개수 조회"""
        count = SkillExtractionService.get_skill_count()

        self.assertIsInstance(count, int)
        self.assertGreater(count, 50)
        self.assertEqual(count, len(MASTER_SKILLS))


class TestBackwardCompatibility(TestCase):
    """하위 호환성 테스트"""

    def test_extract_skills_function(self):
        """기존 extract_skills 함수 호환"""
        text = "Python, Django 경험"
        result = extract_skills(text)

        self.assertIn("Python", result)
        self.assertIn("Django", result)

    def test_extract_skills_from_job_posting_function(self):
        """기존 extract_skills_from_job_posting 함수 호환"""
        required, preferred = extract_skills_from_job_posting("Python 필수", "AWS 우대")

        self.assertIn("Python", required)
        self.assertIn("AWS", preferred)

    def test_get_all_skills_function(self):
        """기존 get_all_skills 함수 호환"""
        skills = get_all_skills()

        self.assertIsInstance(skills, list)
        self.assertGreater(len(skills), 0)

    def test_get_skill_count_function(self):
        """기존 get_skill_count 함수 호환"""
        count = get_skill_count()

        self.assertIsInstance(count, int)
        self.assertGreater(count, 0)


def create_test_job_posting(**kwargs):
    """테스트용 JobPosting 생성"""
    defaults = {
        "url": "http://example.com/job",
        "company_name": "Test Corp",
        "position": "Backend Developer",
        "main_tasks": "",
        "requirements": "",
        "preferred_points": "",
        "location": "서울",
        "district": "강남구",
        "employment_type": "정규직",
        "career_min": 0,
        "career_max": 5,
    }
    defaults.update(kwargs)
    return JobPosting.objects.create(**defaults)


@pytest.mark.django_db
class TestRelatedJobsBySkillView(TestCase):
    """RelatedJobsBySkillView API 테스트"""

    def setUp(self):
        self.client = Client()

    @patch("skill.views.graph_db_client")
    def test_get_related_jobs_by_skill(self, mock_graph_client):
        """스킬 기반 공고 조회 성공"""
        # 테스트 데이터 생성
        job1 = create_test_job_posting(
            posting_id=101, position="Python Developer", requirements="Python, Django"
        )
        job2 = create_test_job_posting(
            posting_id=102, position="Backend Engineer", requirements="Python, FastAPI"
        )

        # Mock 설정
        mock_graph_client.get_jobs_related_to_skill.return_value = [101, 102]

        # API 호출
        response = self.client.get("/api/v1/skills/related/Python/")

        # 검증
        self.assertEqual(response.status_code, 200)
        mock_graph_client.get_jobs_related_to_skill.assert_called_once_with("Python")

        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertIn(data[0]["posting_id"], [101, 102])

    @patch("skill.views.graph_db_client")
    def test_get_related_jobs_no_results(self, mock_graph_client):
        """스킬 매칭 결과 없음"""
        # Mock 설정: 빈 리스트 반환
        mock_graph_client.get_jobs_related_to_skill.return_value = []

        # API 호출
        response = self.client.get("/api/v1/skills/related/UnknownSkill/")

        # 검증
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class TestMasterSkills(TestCase):
    """MASTER_SKILLS 데이터 검증"""

    def test_master_skills_structure(self):
        """마스터 스킬 목록 구조 검증"""
        self.assertIsInstance(MASTER_SKILLS, dict)
        self.assertGreater(len(MASTER_SKILLS), 0)

        # 각 항목이 올바른 구조인지 확인
        for skill_name, patterns in MASTER_SKILLS.items():
            self.assertIsInstance(skill_name, str)
            self.assertIsInstance(patterns, list)
            self.assertGreater(len(patterns), 0)

            for pattern in patterns:
                self.assertIsInstance(pattern, str)

    def test_master_skills_coverage(self):
        """주요 기술 스택 포함 여부"""
        required_skills = [
            "Python",
            "Java",
            "JavaScript",
            "TypeScript",
            "Django",
            "Spring",
            "React",
            "Vue.js",
            "PostgreSQL",
            "MySQL",
            "MongoDB",
            "Redis",
            "AWS",
            "Docker",
            "Kubernetes",
        ]

        for skill in required_skills:
            self.assertIn(skill, MASTER_SKILLS, f"{skill}이 MASTER_SKILLS에 없습니다")

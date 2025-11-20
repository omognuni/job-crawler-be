"""
Tests for SkillExtractionService

스킬 추출 로직 테스트
"""

import pytest
from skill.services import SkillExtractionService


class TestSkillExtractionService:
    """SkillExtractionService 단위 테스트"""

    def test_extract_skills_from_text(self):
        """텍스트에서 스킬 추출"""
        # Given
        text = "Backend developer with Python, Django, and PostgreSQL experience. AWS and Docker skills preferred."

        # When
        skills = SkillExtractionService.extract_skills(text)

        # Then
        assert "Python" in skills
        assert "Django" in skills
        assert "PostgreSQL" in skills
        assert "AWS" in skills
        assert "Docker" in skills

    def test_extract_skills_from_korean_text(self):
        """한글 텍스트에서 스킬 추출"""
        # Given
        text = "백엔드 개발자입니다. 파이썬과 장고를 주로 사용합니다."

        # When
        skills = SkillExtractionService.extract_skills(text)

        # Then
        assert "Python" in skills or "Django" in skills  # 한글 패턴 매칭

    def test_extract_skills_empty_text(self):
        """빈 텍스트 처리"""
        # Given
        text = ""

        # When
        skills = SkillExtractionService.extract_skills(text)

        # Then
        assert skills == []

    def test_extract_skills_from_job_posting(self):
        """채용 공고에서 스킬 추출"""
        # Given
        requirements = "Required: Python, Django, REST API experience"
        preferred_points = "Preferred: AWS, Docker, Kubernetes"
        main_tasks = "Backend development using Python and Django"

        # When
        skills_required, skills_preferred_text = (
            SkillExtractionService.extract_skills_from_job_posting(
                requirements, preferred_points, main_tasks
            )
        )

        # Then
        assert "Python" in skills_required
        assert "Django" in skills_required
        assert "REST API" in skills_required
        assert skills_preferred_text == "Preferred: AWS, Docker, Kubernetes"

    def test_get_all_skills(self):
        """지원하는 모든 스킬 목록 조회"""
        # When
        all_skills = SkillExtractionService.get_all_skills()

        # Then
        assert len(all_skills) > 0
        assert "Python" in all_skills
        assert "Django" in all_skills
        assert "React" in all_skills

    def test_get_skill_count(self):
        """지원하는 스킬 개수 조회"""
        # When
        count = SkillExtractionService.get_skill_count()

        # Then
        assert count > 80  # 80개 이상

    def test_extract_skills_case_insensitive(self):
        """대소문자 구분 없이 스킬 추출"""
        # Given
        text = "PYTHON and python and Python"

        # When
        skills = SkillExtractionService.extract_skills(text)

        # Then
        assert "Python" in skills
        assert skills.count("Python") == 1  # 중복 제거 확인

    def test_extract_skills_with_special_characters(self):
        """특수 문자가 포함된 스킬 추출"""
        # Given
        text = "Experience with C++, C#, and .NET framework"

        # When
        skills = SkillExtractionService.extract_skills(text)

        # Then
        assert "C++" in skills
        assert "C#" in skills

    def test_extract_skills_from_complex_text(self):
        """복잡한 텍스트에서 스킬 추출"""
        # Given
        text = """
        We are looking for a full-stack developer with:
        - Backend: Python, Django, Flask, FastAPI
        - Frontend: React, Vue.js, TypeScript
        - Database: PostgreSQL, MongoDB, Redis
        - DevOps: Docker, Kubernetes, AWS, GCP
        - Tools: Git, Jira, Slack
        """

        # When
        skills = SkillExtractionService.extract_skills(text)

        # Then
        # Backend
        assert "Python" in skills
        assert "Django" in skills
        assert "Flask" in skills
        assert "FastAPI" in skills

        # Frontend
        assert "React" in skills
        assert "Vue.js" in skills
        assert "TypeScript" in skills

        # Database
        assert "PostgreSQL" in skills
        assert "MongoDB" in skills
        assert "Redis" in skills

        # DevOps
        assert "Docker" in skills
        assert "Kubernetes" in skills
        assert "AWS" in skills
        assert "GCP" in skills

        # Tools
        assert "Git" in skills
        assert "Jira" in skills
        assert "Slack" in skills

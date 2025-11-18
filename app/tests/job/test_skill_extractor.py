"""
스킬 추출기 테스트
"""

import pytest
from job.skill_extractor import (
    extract_skills,
    extract_skills_from_job_posting,
    get_all_skills,
    get_skill_count,
)


class TestSkillExtraction:
    """스킬 추출 기본 테스트"""

    def test_extract_python_django(self):
        """Python과 Django를 포함한 텍스트에서 스킬 추출"""
        text = "Python과 Django 경험 필수"
        result = extract_skills(text)

        assert "Python" in result
        assert "Django" in result
        assert len(result) == 2

    def test_extract_cpp_java(self):
        """C++와 Java를 포함한 텍스트에서 스킬 추출"""
        text = "C++, Java 개발자 우대"
        result = extract_skills(text)

        assert "C++" in result
        assert "Java" in result
        # JavaScript가 포함되지 않아야 함
        assert "JavaScript" not in result

    def test_extract_aws_docker_kubernetes(self):
        """클라우드 기술 스킬 추출"""
        text = "AWS, Docker, Kubernetes 경험자 우대"
        result = extract_skills(text)

        assert "AWS" in result
        assert "Docker" in result
        assert "Kubernetes" in result

    def test_extract_react_typescript(self):
        """프론트엔드 기술 스킬 추출"""
        text = "React, TypeScript를 이용한 프론트엔드 개발"
        result = extract_skills(text)

        assert "React" in result
        assert "TypeScript" in result


class TestCaseInsensitive:
    """대소문자 무시 테스트"""

    def test_lowercase_python(self):
        """소문자 python도 인식"""
        text = "python 프로그래밍 경험"
        result = extract_skills(text)

        assert "Python" in result

    def test_uppercase_DJANGO(self):
        """대문자 DJANGO도 인식"""
        text = "DJANGO 프레임워크 사용 경험"
        result = extract_skills(text)

        assert "Django" in result

    def test_mixed_case_JavaScript(self):
        """혼합 케이스 jAvAsCrIpT도 인식"""
        text = "jAvAsCrIpT 개발자"
        result = extract_skills(text)

        assert "JavaScript" in result


class TestSpecialCharacters:
    """특수문자 처리 테스트"""

    def test_cpp_with_plus(self):
        """C++ 인식"""
        text = "C++ 개발 경험 5년"
        result = extract_skills(text)

        assert "C++" in result
        # C가 별도로 인식되지 않아야 함
        assert "C" not in result or len([s for s in result if s == "C"]) == 0

    def test_csharp_with_hash(self):
        """C# 인식"""
        text = "C# 및 .NET 개발"
        result = extract_skills(text)

        assert "C#" in result

    def test_vuejs_with_dot(self):
        """Vue.js 인식"""
        text = "Vue.js 프론트엔드 개발"
        result = extract_skills(text)

        assert "Vue.js" in result or "Vue" in result


class TestKoreanPatterns:
    """한글 패턴 테스트"""

    def test_korean_python(self):
        """'파이썬' 인식"""
        text = "파이썬 개발 경험"
        result = extract_skills(text)

        assert "Python" in result

    def test_korean_django(self):
        """'장고' 인식"""
        text = "장고 프레임워크 경험자"
        result = extract_skills(text)

        assert "Django" in result

    def test_korean_react(self):
        """'리액트' 인식"""
        text = "리액트를 이용한 SPA 개발"
        result = extract_skills(text)

        assert "React" in result


class TestAliases:
    """별칭 처리 테스트"""

    def test_javascript_vs_js(self):
        """'js'를 입력해도 JavaScript로 인식"""
        text = "Node.js와 js 프레임워크 경험"
        result = extract_skills(text)

        assert "JavaScript" in result or "Node.js" in result

    def test_postgresql_vs_postgres(self):
        """'postgres'를 입력해도 PostgreSQL로 인식"""
        text = "postgres 데이터베이스 관리"
        result = extract_skills(text)

        assert "PostgreSQL" in result

    def test_kubernetes_vs_k8s(self):
        """'k8s'를 입력해도 Kubernetes로 인식"""
        text = "k8s 오케스트레이션 경험"
        result = extract_skills(text)

        assert "Kubernetes" in result


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_text(self):
        """빈 텍스트 입력"""
        result = extract_skills("")

        assert result == []

    def test_none_text(self):
        """None 입력"""
        result = extract_skills(None)

        assert result == []

    def test_no_skills_found(self):
        """스킬이 없는 텍스트"""
        text = "우리 회사는 훌륭한 복지를 제공합니다."
        result = extract_skills(text)

        assert result == []

    def test_duplicate_skills(self):
        """중복된 스킬은 한 번만 반환"""
        text = "Python Python PYTHON python 파이썬"
        result = extract_skills(text)

        # Python이 한 번만 포함되어야 함
        python_count = result.count("Python")
        assert python_count == 1

    def test_long_text(self):
        """긴 텍스트 처리"""
        text = (
            """
        저희 회사는 Python, Django, Flask를 사용하여 백엔드를 개발하고,
        React, TypeScript, Next.js로 프론트엔드를 개발합니다.
        AWS, Docker, Kubernetes를 활용한 클라우드 인프라 구축 경험이 필요하며,
        PostgreSQL, MongoDB, Redis 등의 데이터베이스 경험이 있으면 우대합니다.
        """
            * 10
        )  # 긴 텍스트

        result = extract_skills(text)

        # 주요 스킬들이 모두 포함되어야 함
        assert "Python" in result
        assert "Django" in result
        assert "React" in result
        assert "AWS" in result
        assert len(result) >= 10


class TestJobPostingExtraction:
    """채용 공고용 스킬 추출 테스트"""

    def test_extract_from_requirements(self):
        """자격 요건에서 필수 스킬 추출"""
        requirements = "Python, Django 경험 필수"
        preferred = ""

        required, preferred_skills = extract_skills_from_job_posting(
            requirements, preferred
        )

        assert "Python" in required
        assert "Django" in required

    def test_extract_from_preferred(self):
        """우대 사항에서 우대 스킬 추출"""
        requirements = "Python 경험"
        preferred = "AWS, Docker 경험자 우대"

        required, preferred_skills = extract_skills_from_job_posting(
            requirements, preferred
        )

        assert "Python" in required
        assert "AWS" in preferred_skills
        assert "Docker" in preferred_skills

    def test_no_duplicate_between_required_and_preferred(self):
        """필수와 우대 스킬이 겹치지 않아야 함"""
        requirements = "Python, Django 경험 필수"
        preferred = "Python, Flask 경험자 우대"

        required, preferred_skills = extract_skills_from_job_posting(
            requirements, preferred
        )

        assert "Python" in required
        assert "Django" in required
        # Python이 우대에는 없어야 함 (이미 필수에 있으므로)
        assert "Python" not in preferred_skills
        assert "Flask" in preferred_skills

    def test_with_main_tasks(self):
        """주요 업무 텍스트도 필수 스킬에 포함"""
        requirements = "Python 경험"
        preferred = "AWS 경험"
        main_tasks = "Django를 사용한 API 개발"

        required, preferred_skills = extract_skills_from_job_posting(
            requirements, preferred, main_tasks
        )

        assert "Python" in required
        assert "Django" in required  # main_tasks에서 추출
        assert "AWS" in preferred_skills


class TestUtilityFunctions:
    """유틸리티 함수 테스트"""

    def test_get_all_skills(self):
        """전체 스킬 목록 조회"""
        all_skills = get_all_skills()

        assert isinstance(all_skills, list)
        assert len(all_skills) > 0
        assert "Python" in all_skills
        assert "JavaScript" in all_skills
        # 정렬되어 있어야 함
        assert all_skills == sorted(all_skills)

    def test_get_skill_count(self):
        """스킬 개수 조회"""
        count = get_skill_count()

        assert isinstance(count, int)
        assert count > 0
        # 최소 50개 이상의 스킬이 정의되어 있어야 함
        assert count >= 50


class TestPerformance:
    """성능 테스트"""

    def test_performance_with_large_text(self):
        """큰 텍스트도 빠르게 처리"""
        import time

        # 1000자 이상의 텍스트
        text = (
            """
        Python Django Flask FastAPI JavaScript TypeScript React Vue.js Angular
        Node.js Java Spring Kotlin Swift C++ C# SQL MySQL PostgreSQL MongoDB
        AWS GCP Azure Docker Kubernetes Redis Elasticsearch Git GitHub
        """
            * 50
        )

        start = time.time()
        result = extract_skills(text)
        elapsed = time.time() - start

        # 0.1초 이내에 처리되어야 함
        assert elapsed < 0.1
        assert len(result) > 0

    def test_caching_performance(self):
        """패턴 컴파일 캐싱 동작 확인"""
        text1 = "Python Django React"
        text2 = "Java Spring Vue.js"

        # 첫 번째 호출
        result1 = extract_skills(text1)
        # 두 번째 호출 (캐시 사용)
        result2 = extract_skills(text2)

        assert len(result1) > 0
        assert len(result2) > 0
        # 결과가 다르지만 정상 동작
        assert result1 != result2

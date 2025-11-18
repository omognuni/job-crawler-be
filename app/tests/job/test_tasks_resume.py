"""
4단계 테스트: Resume 수집 파이프라인 개편

이 테스트 모듈은 다음을 검증합니다:
1. process_resume 태스크 단위 테스트
2. Resume.save() 통합 테스트
3. AI 응답 파싱 테스트
4. 재귀 호출 방지 테스트
"""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.utils import timezone
from job.models import Resume
from job.tasks import process_resume


class TestProcessResumeTask:
    """process_resume 태스크 단위 테스트"""

    @pytest.mark.django_db
    def test_process_resume_success_with_llm(self, celery_eager_mode):
        """LLM을 사용한 정상적인 Resume 처리 테스트"""
        # Given: Resume 생성
        resume = Resume.objects.create(
            user_id=1001,
            content="""
            이름: 김개발
            경력: 5년
            기술 스택: Python, Django, FastAPI, PostgreSQL, AWS

            주요 프로젝트:
            - 전자상거래 플랫폼 백엔드 개발 (Django, PostgreSQL)
            - RESTful API 설계 및 구현 (FastAPI)
            - AWS 인프라 구축 및 관리

            강점: 백엔드 개발 전문가, 클라우드 아키텍처 설계 경험
            """,
            content_hash="",
        )

        # Mock external dependencies
        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("os.getenv") as mock_getenv,
            patch("google.genai.Client") as mock_client_class,
        ):

            # Mock environment
            mock_getenv.return_value = "test_api_key"

            # Mock LLM response
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            mock_response = Mock()
            mock_response.text = json.dumps(
                {
                    "career_years": 5,
                    "strengths": "백엔드 개발 전문가",
                    "experience_summary": "5년 경력의 백엔드 개발자. Python, Django, FastAPI를 활용한 전자상거래 플랫폼 개발 및 AWS 인프라 구축 경험.",
                }
            )
            mock_client.models.generate_content.return_value = mock_response

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When: 태스크 실행
            result = process_resume(1001)

            # Then: 결과 검증
            assert result["success"] is True
            assert result["user_id"] == 1001
            assert result["skills_count"] > 0
            assert result["career_years"] == 5

            # Resume 업데이트 확인
            resume.refresh_from_db()
            assert resume.analysis_result is not None
            assert resume.analysis_result["skills"] is not None
            assert resume.analysis_result["career_years"] == 5
            assert resume.analysis_result["strengths"] == "백엔드 개발 전문가"
            assert resume.experience_summary is not None
            assert "5년 경력" in resume.experience_summary
            assert resume.analyzed_at is not None

            # ChromaDB upsert 호출 확인
            mock_vector_db.get_or_create_collection.assert_called_once_with("resumes")
            mock_vector_db.upsert_documents.assert_called_once()

    @pytest.mark.django_db
    def test_process_resume_without_api_key(self, celery_eager_mode):
        """API 키 없이 Resume 처리 (Fallback) 테스트"""
        # Given
        resume = Resume.objects.create(
            user_id=1002,
            content="Python, Django 개발자. 3년 경력.",
            content_hash="",
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("os.getenv") as mock_getenv,
        ):

            # API 키 없음
            mock_getenv.return_value = None

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            result = process_resume(1002)

            # Then: Fallback으로 처리
            assert result["success"] is True
            assert result["user_id"] == 1002

            resume.refresh_from_db()
            assert resume.analysis_result is not None
            assert resume.analysis_result["career_years"] == 0  # Fallback value
            assert "API 키 미설정" in resume.analysis_result["strengths"]
            assert resume.experience_summary is not None

    @pytest.mark.django_db
    def test_process_resume_skill_extraction(self, celery_eager_mode):
        """스킬 추출 검증"""
        # Given: 다양한 스킬이 포함된 Resume
        resume = Resume.objects.create(
            user_id=1003,
            content="""
            풀스택 개발자

            기술 스택:
            - Frontend: React, TypeScript, Vue.js
            - Backend: Java, Spring Boot, Node.js
            - Database: MySQL, MongoDB, Redis
            - DevOps: Docker, Kubernetes, Jenkins

            5년 경력의 시니어 개발자
            """,
            content_hash="",
        )

        with (
            patch("job.tasks.vector_db_client"),
            patch("os.getenv", return_value=None),
        ):  # Fallback mode

            # When
            result = process_resume(1003)

            # Then: 스킬 추출 확인
            resume.refresh_from_db()
            skills = resume.analysis_result["skills"]

            # Frontend 스킬
            assert "React" in skills
            assert "TypeScript" in skills
            assert "Vue.js" in skills

            # Backend 스킬
            assert "Java" in skills
            assert "Spring Boot" in skills

            # Database 스킬
            assert "MySQL" in skills
            assert "MongoDB" in skills
            assert "Redis" in skills

            # DevOps 스킬
            assert "Docker" in skills
            assert "Kubernetes" in skills
            assert "Jenkins" in skills

    @pytest.mark.django_db
    def test_process_resume_needs_analysis_skip(self, celery_eager_mode):
        """needs_analysis() 체크 - 재분석 불필요 시 스킵"""
        # Given: 이미 분석된 Resume
        resume = Resume.objects.create(
            user_id=1004,
            content="Python 개발자",
            content_hash="",
            analysis_result={"skills": ["Python"], "career_years": 3},
            analyzed_at=timezone.now(),
        )
        # 해시 계산
        resume.content_hash = resume.calculate_hash()
        resume.save(update_fields=["content_hash"])

        # When: 동일한 content로 처리 시도
        result = process_resume(1004)

        # Then: 스킵됨
        assert result["success"] is True
        assert result["skipped"] is True
        assert result["reason"] == "No changes detected"

    @pytest.mark.django_db
    def test_process_resume_chromadb_upsert(self, celery_eager_mode):
        """ChromaDB upsert 호출 검증"""
        # Given
        resume = Resume.objects.create(
            user_id=1005,
            content="데이터 엔지니어, Python, Spark, Airflow 경험 5년",
            content_hash="",
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("os.getenv") as mock_getenv,
            patch("google.genai.Client") as mock_client_class,
        ):

            mock_getenv.return_value = "test_api_key"

            # Mock LLM response
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_response = Mock()
            mock_response.text = json.dumps(
                {
                    "career_years": 5,
                    "strengths": "데이터 파이프라인 전문가",
                    "experience_summary": "5년 경력의 데이터 엔지니어. Python, Spark, Airflow를 활용한 데이터 파이프라인 구축 경험.",
                }
            )
            mock_client.models.generate_content.return_value = mock_response

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            process_resume(1005)

            # Then: upsert_documents 호출 인자 검증
            call_args = mock_vector_db.upsert_documents.call_args
            assert call_args is not None

            # documents 인자 확인
            documents = call_args.kwargs["documents"]
            assert len(documents) == 1
            experience_summary = documents[0]
            assert "5년 경력" in experience_summary
            assert "데이터 엔지니어" in experience_summary

            # metadatas 인자 확인
            metadatas = call_args.kwargs["metadatas"]
            assert len(metadatas) == 1
            metadata = metadatas[0]
            assert metadata["career_years"] == 5
            assert metadata["skills_count"] > 0

            # ids 인자 확인
            ids = call_args.kwargs["ids"]
            assert ids == ["1005"]

    @pytest.mark.django_db
    def test_process_resume_nonexistent_user(self, celery_eager_mode):
        """존재하지 않는 user_id 처리 테스트"""
        # Given: 존재하지 않는 ID
        nonexistent_id = 99999

        # When
        result = process_resume(nonexistent_id)

        # Then: 에러 결과 반환
        assert result["success"] is False
        assert "not found" in result["error"]
        assert str(nonexistent_id) in result["error"]

    @pytest.mark.django_db
    def test_process_resume_retry_on_error(self, celery_eager_mode):
        """DB 연결 오류 시 재시도 로직 테스트"""
        # Given
        resume = Resume.objects.create(
            user_id=1006,
            content="개발자",
            content_hash="",
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("os.getenv", return_value=None),
        ):

            # ChromaDB 연결 오류 시뮬레이션
            mock_vector_db.get_or_create_collection.side_effect = Exception(
                "Connection error"
            )

            # When: 태스크 실행 (eager 모드에서는 예외 발생)
            try:
                result = process_resume(1006)
                assert False, "Should raise exception"
            except Exception as e:
                # Then: 예외 발생 확인
                assert "Connection error" in str(e) or "Connection error" in str(
                    e.__cause__
                )


class TestResumeSaveIntegration:
    """Resume.save() 통합 테스트"""

    @pytest.mark.django_db
    def test_resume_save_triggers_task(self, celery_eager_mode):
        """Resume 저장 시 Celery 태스크 큐에 추가되는지 확인"""
        # transaction.on_commit이 호출되는지 확인
        with patch("django.db.transaction.on_commit") as mock_on_commit:
            # Given & When: Resume 생성
            resume = Resume.objects.create(
                user_id=2001,
                content="Python 개발자 5년 경력",
                content_hash="",
            )

            # Then: transaction.on_commit이 호출되었는지 확인
            mock_on_commit.assert_called_once()

    @pytest.mark.django_db
    def test_resume_update_content_triggers_task(self, celery_eager_mode):
        """Resume content 업데이트 시 태스크 트리거 확인"""
        # Given: 기존 Resume (첫 생성 시 태스크 트리거 방지)
        with patch("django.db.transaction.on_commit"):
            resume = Resume.objects.create(
                user_id=2002,
                content="Python 개발자",
                content_hash="",
            )
            # 해시 설정
            resume.content_hash = resume.calculate_hash()
            resume.save(update_fields=["content_hash"])

        # When: content 업데이트 시 태스크 트리거
        with patch("django.db.transaction.on_commit") as mock_on_commit:
            resume.content = "Python 개발자 5년 경력 추가"
            resume.save()

            # Then: transaction.on_commit이 호출되었는지 확인
            mock_on_commit.assert_called_once()

    @pytest.mark.django_db
    def test_resume_same_content_skips_task(self, celery_eager_mode):
        """동일한 content 저장 시 태스크 스킵 확인"""
        # Given: 기존 Resume
        with patch("django.db.transaction.on_commit"):
            resume = Resume.objects.create(
                user_id=2003,
                content="Python 개발자",
                content_hash="",
            )
            resume.content_hash = resume.calculate_hash()
            resume.save(update_fields=["content_hash"])

        # When: 동일한 content로 저장
        with patch("django.db.transaction.on_commit") as mock_on_commit:
            # content 변경 없이 저장
            resume.save()

            # Then: transaction.on_commit 호출 안 됨 (해시 동일)
            mock_on_commit.assert_not_called()

    @pytest.mark.django_db
    def test_resume_analysis_only_update_skips_task(self, celery_eager_mode):
        """분석 결과 필드만 업데이트 시 태스크 스킵 확인 (무한 루프 방지)"""
        # Given: 기존 Resume
        with patch("django.db.transaction.on_commit"):
            resume = Resume.objects.create(
                user_id=2004,
                content="Python 개발자",
                content_hash="",
            )

        # When: 분석 결과 필드만 업데이트
        with patch("django.db.transaction.on_commit") as mock_on_commit:
            resume.analysis_result = {"skills": ["Python"], "career_years": 5}
            resume.experience_summary = "5년 경력 Python 개발자"
            resume.analyzed_at = timezone.now()
            resume.save(
                update_fields=[
                    "analysis_result",
                    "experience_summary",
                    "analyzed_at",
                    "content_hash",
                ]
            )

            # Then: transaction.on_commit 호출 안 됨
            mock_on_commit.assert_not_called()

    @pytest.mark.django_db
    def test_resume_calculate_hash(self):
        """해시값 계산 테스트"""
        # Given
        content1 = "Python 개발자"
        content2 = "Python 개발자"
        content3 = "Java 개발자"

        resume1 = Resume(user_id=3001, content=content1, content_hash="")
        resume2 = Resume(user_id=3002, content=content2, content_hash="")
        resume3 = Resume(user_id=3003, content=content3, content_hash="")

        # When
        hash1 = resume1.calculate_hash()
        hash2 = resume2.calculate_hash()
        hash3 = resume3.calculate_hash()

        # Then
        assert hash1 == hash2  # 동일한 content
        assert hash1 != hash3  # 다른 content
        assert len(hash1) == 64  # SHA256 해시 길이

    @pytest.mark.django_db
    def test_resume_needs_analysis_logic(self):
        """needs_analysis() 로직 테스트"""
        # Case 1: 새로운 Resume (분석 필요)
        resume1 = Resume.objects.create(
            user_id=3004,
            content="Python 개발자",
            content_hash="wrong_hash",
        )
        assert resume1.needs_analysis() is True

        # Case 2: analysis_result 없음 (분석 필요)
        resume2 = Resume.objects.create(
            user_id=3005,
            content="Java 개발자",
            content_hash="",
        )
        resume2.content_hash = resume2.calculate_hash()
        resume2.save(update_fields=["content_hash"])
        assert resume2.needs_analysis() is True

        # Case 3: analyzed_at 없음 (분석 필요)
        resume3 = Resume.objects.create(
            user_id=3006,
            content="Go 개발자",
            content_hash="",
            analysis_result={"skills": ["Go"]},
        )
        resume3.content_hash = resume3.calculate_hash()
        resume3.save(update_fields=["content_hash"])
        assert resume3.needs_analysis() is True

        # Case 4: 모든 조건 충족 (분석 불필요)
        resume4 = Resume.objects.create(
            user_id=3007,
            content="Rust 개발자",
            content_hash="",
            analysis_result={"skills": ["Rust"]},
            analyzed_at=timezone.now(),
        )
        resume4.content_hash = resume4.calculate_hash()
        resume4.save(update_fields=["content_hash"])
        assert resume4.needs_analysis() is False


class TestAIResponseParsing:
    """AI 응답 파싱 테스트"""

    @pytest.mark.django_db
    def test_parse_normal_json_response(self, celery_eager_mode):
        """정상 JSON 응답 처리"""
        # Given
        resume = Resume.objects.create(
            user_id=4001,
            content="Python 개발자 3년 경력",
            content_hash="",
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("os.getenv") as mock_getenv,
            patch("google.genai.Client") as mock_client_class,
        ):

            mock_getenv.return_value = "test_api_key"

            # Mock LLM response (정상 JSON)
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_response = Mock()
            mock_response.text = json.dumps(
                {
                    "career_years": 3,
                    "strengths": "백엔드 개발",
                    "experience_summary": "3년 경력의 백엔드 개발자",
                }
            )
            mock_client.models.generate_content.return_value = mock_response

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            result = process_resume(4001)

            # Then
            assert result["success"] is True
            resume.refresh_from_db()
            assert resume.analysis_result["career_years"] == 3
            assert resume.analysis_result["strengths"] == "백엔드 개발"
            assert resume.experience_summary == "3년 경력의 백엔드 개발자"

    @pytest.mark.django_db
    def test_parse_json_with_code_block(self, celery_eager_mode):
        """JSON 코드 블록이 포함된 응답 처리"""
        # Given
        resume = Resume.objects.create(
            user_id=4002,
            content="Java 개발자 2년 경력",
            content_hash="",
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("os.getenv") as mock_getenv,
            patch("google.genai.Client") as mock_client_class,
        ):

            mock_getenv.return_value = "test_api_key"

            # Mock LLM response (```json 코드 블록 포함)
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_response = Mock()
            mock_response.text = f"""```json
{json.dumps({
    "career_years": 2,
    "strengths": "Java/Spring 개발",
    "experience_summary": "2년 경력의 Java 개발자"
})}
```"""
            mock_client.models.generate_content.return_value = mock_response

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            result = process_resume(4002)

            # Then: 코드 블록이 제거되고 정상 파싱됨
            assert result["success"] is True
            resume.refresh_from_db()
            assert resume.analysis_result["career_years"] == 2

    @pytest.mark.django_db
    def test_parse_incomplete_json_response(self, celery_eager_mode):
        """불완전한 JSON 응답 처리 (Fallback)"""
        # Given
        resume = Resume.objects.create(
            user_id=4003,
            content="JavaScript 개발자",
            content_hash="",
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("os.getenv") as mock_getenv,
            patch("google.genai.Client") as mock_client_class,
        ):

            mock_getenv.return_value = "test_api_key"

            # Mock LLM response (잘못된 JSON)
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_response = Mock()
            mock_response.text = "Invalid JSON response"
            mock_client.models.generate_content.return_value = mock_response

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            result = process_resume(4003)

            # Then: Fallback으로 처리됨
            assert result["success"] is True
            resume.refresh_from_db()
            assert resume.analysis_result is not None
            assert "JavaScript" in resume.analysis_result["skills"]

    @pytest.mark.django_db
    def test_parse_llm_exception(self, celery_eager_mode):
        """LLM 호출 실패 시 Fallback 처리"""
        # Given
        resume = Resume.objects.create(
            user_id=4004,
            content="TypeScript 개발자",
            content_hash="",
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("os.getenv") as mock_getenv,
            patch("google.genai.Client") as mock_client_class,
        ):

            mock_getenv.return_value = "test_api_key"

            # Mock LLM 예외
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.side_effect = Exception("LLM API Error")

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            result = process_resume(4004)

            # Then: Fallback으로 처리됨
            assert result["success"] is True
            resume.refresh_from_db()
            assert resume.analysis_result is not None
            assert "TypeScript" in resume.analysis_result["skills"]


class TestInfiniteLoopPrevention:
    """재귀 호출 방지 테스트"""

    @pytest.mark.django_db
    def test_update_fields_prevents_infinite_loop(self, celery_eager_mode):
        """update_fields 사용 시 무한루프 방지 확인"""
        # Given: Resume 생성
        with patch("django.db.transaction.on_commit"):
            resume = Resume.objects.create(
                user_id=5001,
                content="Python 개발자",
                content_hash="",
            )

        # When: analysis_result, experience_summary 업데이트 (태스크 내부에서 수행)
        with patch("django.db.transaction.on_commit") as mock_on_commit:
            resume.analysis_result = {"skills": ["Python"], "career_years": 5}
            resume.experience_summary = "5년 경력 개발자"
            resume.analyzed_at = timezone.now()
            resume.save(
                update_fields=[
                    "analysis_result",
                    "experience_summary",
                    "analyzed_at",
                    "content_hash",
                ]
            )

            # Then: 태스크 재호출 안 됨
            mock_on_commit.assert_not_called()

    @pytest.mark.django_db
    def test_partial_update_fields_triggers_task(self, celery_eager_mode):
        """일부 필드만 포함된 update_fields는 태스크 트리거"""
        # Given
        with patch("django.db.transaction.on_commit"):
            resume = Resume.objects.create(
                user_id=5002,
                content="Java 개발자",
                content_hash="",
            )
            resume.content_hash = resume.calculate_hash()
            resume.save(update_fields=["content_hash"])

        # When: content도 함께 업데이트
        with patch("django.db.transaction.on_commit") as mock_on_commit:
            resume.content = "Java 개발자 경력 추가"
            resume.analysis_result = {"skills": ["Java"]}
            resume.save(update_fields=["content", "analysis_result"])

            # Then: 태스크 트리거됨 (content가 포함되어 있음)
            mock_on_commit.assert_called_once()

    @pytest.mark.django_db
    def test_full_save_with_changed_hash_triggers_task(self, celery_eager_mode):
        """해시값 변경된 전체 저장 시 태스크 트리거"""
        # Given
        with patch("django.db.transaction.on_commit"):
            resume = Resume.objects.create(
                user_id=5003,
                content="Go 개발자",
                content_hash="",
            )
            resume.content_hash = resume.calculate_hash()
            resume.save(update_fields=["content_hash"])

        # When: content 변경 후 전체 저장
        with patch("django.db.transaction.on_commit") as mock_on_commit:
            resume.content = "Go 개발자 5년 경력"
            resume.save()  # update_fields 없음

            # Then: 태스크 트리거됨
            mock_on_commit.assert_called_once()


class TestEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.mark.django_db
    def test_resume_with_empty_content(self, celery_eager_mode):
        """빈 content의 Resume 처리"""
        # Given
        resume = Resume.objects.create(
            user_id=6001,
            content="",
            content_hash="",
        )

        with patch("job.tasks.vector_db_client"), patch("os.getenv", return_value=None):

            # When
            result = process_resume(6001)

            # Then: 성공하지만 스킬 없음
            assert result["success"] is True
            resume.refresh_from_db()
            assert resume.analysis_result["skills"] == []

    @pytest.mark.django_db
    def test_resume_with_very_long_content(self, celery_eager_mode):
        """매우 긴 content의 Resume 처리 (LLM 입력 제한)"""
        # Given: 5000자 이상의 긴 content
        long_content = "Python 개발자. " * 500  # 5000+ chars
        resume = Resume.objects.create(
            user_id=6002,
            content=long_content,
            content_hash="",
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("os.getenv") as mock_getenv,
            patch("google.genai.Client") as mock_client_class,
        ):

            mock_getenv.return_value = "test_api_key"

            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_response = Mock()
            mock_response.text = json.dumps(
                {
                    "career_years": 5,
                    "strengths": "Python 개발",
                    "experience_summary": "경력 많은 Python 개발자",
                }
            )
            mock_client.models.generate_content.return_value = mock_response

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            result = process_resume(6002)

            # Then: 정상 처리 (3000자로 잘림)
            assert result["success"] is True

            # LLM 호출 시 3000자로 제한되었는지 확인
            call_args = mock_client.models.generate_content.call_args
            prompt = call_args.kwargs["contents"]
            # content[:3000] 사용 확인
            assert len(prompt) < len(long_content)

    @pytest.mark.django_db
    def test_resume_with_no_skills(self, celery_eager_mode):
        """기술 스택이 없는 Resume 처리"""
        # Given
        resume = Resume.objects.create(
            user_id=6003,
            content="일반 사무직 경력 3년. 문서 작성 및 관리.",
            content_hash="",
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("os.getenv", return_value=None),
        ):

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            result = process_resume(6003)

            # Then
            assert result["success"] is True
            assert result["skills_count"] == 0

            resume.refresh_from_db()
            assert resume.analysis_result["skills"] == []

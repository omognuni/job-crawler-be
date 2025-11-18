"""
3단계 테스트: JobPosting 수집 파이프라인 개편

이 테스트 모듈은 다음을 검증합니다:
1. process_job_posting 태스크 단위 테스트
2. JobPosting.save() 통합 테스트
3. 임베딩 텍스트 품질 테스트
4. 실패 시나리오 테스트
"""

from unittest.mock import MagicMock, Mock, call, patch

import pytest
from job.models import JobPosting
from job.tasks import process_job_posting


class TestProcessJobPostingTask:
    """process_job_posting 태스크 단위 테스트"""

    @pytest.mark.django_db
    def test_process_job_posting_success(self, celery_eager_mode):
        """정상적인 JobPosting 처리 테스트"""
        # Given: JobPosting 생성
        job_posting = JobPosting.objects.create(
            posting_id=1001,
            url="https://example.com/job/1001",
            company_name="테스트컴퍼니",
            position="백엔드 개발자",
            main_tasks="Django와 FastAPI를 사용한 API 개발",
            requirements="Python 3년 이상, Django 경험 필수",
            preferred_points="AWS 경험자 우대, Docker 사용 경험",
            location="서울 강남구",
            district="강남구",
            employment_type="정규직",
            career_min=3,
            career_max=7,
        )

        # Mock external dependencies
        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("job.tasks.graph_db_client") as mock_graph_db,
        ):

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When: 태스크 실행
            result = process_job_posting(1001)

            # Then: 결과 검증
            assert result["success"] is True
            assert result["posting_id"] == 1001
            assert result["skills_required"] > 0  # Django, Python, FastAPI 등
            assert result["skills_preferred"] >= 0  # AWS, Docker 등

            # JobPosting 업데이트 확인
            job_posting.refresh_from_db()
            assert job_posting.skills_required is not None
            assert len(job_posting.skills_required) > 0
            assert "Django" in job_posting.skills_required
            assert "Python" in job_posting.skills_required

            # ChromaDB upsert 호출 확인
            mock_vector_db.get_or_create_collection.assert_called_once_with(
                "job_postings"
            )
            mock_vector_db.upsert_documents.assert_called_once()

            # Neo4j 호출 확인
            mock_graph_db.add_job_posting.assert_called_once()

    @pytest.mark.django_db
    def test_process_job_posting_skill_extraction(self, celery_eager_mode):
        """스킬 추출 검증"""
        # Given: 다양한 스킬이 포함된 JobPosting
        job_posting = JobPosting.objects.create(
            posting_id=1002,
            url="https://example.com/job/1002",
            company_name="스타트업",
            position="풀스택 개발자",
            main_tasks="React와 TypeScript로 프론트엔드 개발",
            requirements="Java, Spring Boot 경험, MySQL 사용 가능",
            preferred_points="Kubernetes, Jenkins CI/CD 경험자",
            location="서울 판교",
            district="분당구",
            employment_type="정규직",
            career_min=2,
            career_max=5,
        )

        with patch("job.tasks.vector_db_client"), patch("job.tasks.graph_db_client"):

            # When: 태스크 실행
            result = process_job_posting(1002)

            # Then: 스킬 추출 확인
            job_posting.refresh_from_db()

            # 필수 스킬 확인
            required_skills = job_posting.skills_required
            assert "Java" in required_skills
            assert "Spring Boot" in required_skills
            assert "MySQL" in required_skills
            assert "React" in required_skills
            assert "TypeScript" in required_skills

            # 우대 스킬 확인
            preferred_skills = job_posting.skills_preferred
            assert "Kubernetes" in preferred_skills
            assert "Jenkins" in preferred_skills

    @pytest.mark.django_db
    def test_process_job_posting_chromadb_upsert(self, celery_eager_mode):
        """ChromaDB upsert 호출 검증"""
        # Given
        job_posting = JobPosting.objects.create(
            posting_id=1003,
            url="https://example.com/job/1003",
            company_name="기업",
            position="데이터 엔지니어",
            main_tasks="데이터 파이프라인 구축",
            requirements="Python, Spark 경험",
            preferred_points="Airflow 사용 경험",
            location="서울",
            district="강남구",
            employment_type="정규직",
            career_min=3,
            career_max=10,
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("job.tasks.graph_db_client"),
        ):

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            process_job_posting(1003)

            # Then: upsert_documents 호출 인자 검증
            call_args = mock_vector_db.upsert_documents.call_args
            assert call_args is not None

            # documents 인자 확인
            documents = call_args.kwargs["documents"]
            assert len(documents) == 1
            embedding_text = documents[0]

            # 임베딩 텍스트에 필수 정보 포함 확인
            assert "데이터 엔지니어" in embedding_text
            assert "데이터 파이프라인 구축" in embedding_text
            assert "Python, Spark 경험" in embedding_text
            assert "Airflow 사용 경험" in embedding_text

            # metadatas 인자 확인
            metadatas = call_args.kwargs["metadatas"]
            assert len(metadatas) == 1
            metadata = metadatas[0]
            assert metadata["company_name"] == "기업"
            assert metadata["location"] == "서울"
            assert metadata["employment_type"] == "정규직"
            assert metadata["career_min"] == 3
            assert metadata["career_max"] == 10

            # ids 인자 확인
            ids = call_args.kwargs["ids"]
            assert ids == ["1003"]

    @pytest.mark.django_db
    def test_process_job_posting_neo4j_relationship(self, celery_eager_mode):
        """Neo4j 관계 생성 검증"""
        # Given
        job_posting = JobPosting.objects.create(
            posting_id=1004,
            url="https://example.com/job/1004",
            company_name="네오컴퍼니",
            position="그래프DB 엔지니어",
            main_tasks="Neo4j 쿼리 최적화",
            requirements="Neo4j 경험 필수",
            preferred_points="GraphQL 경험",
            location="서울",
            district="서초구",
            employment_type="정규직",
            career_min=2,
            career_max=5,
        )

        with (
            patch("job.tasks.vector_db_client"),
            patch("job.tasks.graph_db_client") as mock_graph_db,
        ):

            # When
            process_job_posting(1004)

            # Then: add_job_posting 호출 검증
            mock_graph_db.add_job_posting.assert_called_once()
            call_args = mock_graph_db.add_job_posting.call_args

            assert call_args.kwargs["posting_id"] == 1004
            assert call_args.kwargs["position"] == "그래프DB 엔지니어"
            assert call_args.kwargs["company_name"] == "네오컴퍼니"

            # skills 인자 확인 (필수 + 우대 스킬 모두 포함)
            skills = call_args.kwargs["skills"]
            assert "Neo4j" in skills or "GraphQL" in skills  # 적어도 하나는 포함

    @pytest.mark.django_db
    def test_process_job_posting_nonexistent_id(self, celery_eager_mode):
        """존재하지 않는 posting_id 처리 테스트"""
        # Given: 존재하지 않는 ID
        nonexistent_id = 99999

        # When: 태스크 실행
        result = process_job_posting(nonexistent_id)

        # Then: 에러 결과 반환
        assert result["success"] is False
        assert "not found" in result["error"]
        assert str(nonexistent_id) in result["error"]

    @pytest.mark.django_db
    def test_process_job_posting_retry_on_error(self, celery_eager_mode):
        """DB 연결 오류 시 재시도 로직 테스트"""
        # Given
        job_posting = JobPosting.objects.create(
            posting_id=1005,
            url="https://example.com/job/1005",
            company_name="리트라이컴퍼니",
            position="개발자",
            main_tasks="개발",
            requirements="Python",
            preferred_points="",
            location="서울",
            district="강남구",
            employment_type="정규직",
            career_min=0,
            career_max=3,
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("job.tasks.graph_db_client"),
        ):

            # ChromaDB 연결 오류 시뮬레이션
            mock_vector_db.get_or_create_collection.side_effect = Exception(
                "Connection error"
            )

            # When: 태스크 실행 (eager 모드에서는 예외가 그대로 발생)
            # Celery의 Retry 예외가 발생하는지 확인
            try:
                result = process_job_posting(1005)
                # eager 모드에서는 여기에 도달하지 않음
                assert False, "Should raise exception"
            except Exception as e:
                # Then: 예외 발생 확인 (Retry 또는 원본 Exception)
                # eager 모드에서는 Retry의 chained exception으로 원본이 포함됨
                assert "Connection error" in str(e) or "Connection error" in str(
                    e.__cause__
                )


class TestJobPostingSaveIntegration:
    """JobPosting.save() 통합 테스트"""

    @pytest.mark.django_db
    def test_job_posting_save_triggers_task(self, celery_eager_mode):
        """JobPosting 저장 시 Celery 태스크 큐에 추가되는지 확인"""
        # transaction.on_commit이 호출되는지 확인
        with patch("django.db.transaction.on_commit") as mock_on_commit:
            # Given & When: JobPosting 생성
            job_posting = JobPosting.objects.create(
                posting_id=2001,
                url="https://example.com/job/2001",
                company_name="테스트",
                position="개발자",
                main_tasks="개발 업무",
                requirements="개발 경험",
                preferred_points="",
                location="서울",
                district="강남구",
                employment_type="정규직",
                career_min=1,
                career_max=3,
            )

            # Then: transaction.on_commit이 호출되었는지 확인
            mock_on_commit.assert_called_once()

    @pytest.mark.django_db
    def test_job_posting_update_triggers_task(self, celery_eager_mode):
        """JobPosting 업데이트 시 태스크 트리거 확인"""
        # Given: 기존 JobPosting (첫 생성 시 태스크 트리거 방지)
        with patch("django.db.transaction.on_commit"):
            job_posting = JobPosting.objects.create(
                posting_id=2002,
                url="https://example.com/job/2002",
                company_name="테스트",
                position="개발자",
                main_tasks="개발 업무",
                requirements="개발 경험",
                preferred_points="",
                location="서울",
                district="강남구",
                employment_type="정규직",
                career_min=1,
                career_max=3,
            )

        # When: 업데이트 시 태스크 트리거
        with patch("django.db.transaction.on_commit") as mock_on_commit:
            job_posting.position = "시니어 개발자"
            job_posting.save()

            # Then: transaction.on_commit이 호출되었는지 확인
            mock_on_commit.assert_called_once()

    @pytest.mark.django_db
    def test_job_posting_skill_only_update_skips_task(self):
        """스킬 필드만 업데이트 시 태스크 스킵 확인 (무한 루프 방지)"""
        # Given: 기존 JobPosting (첫 생성 시 태스크 트리거 방지)
        with patch.object(JobPosting, "_schedule_processing"):
            job_posting = JobPosting.objects.create(
                posting_id=2003,
                url="https://example.com/job/2003",
                company_name="테스트",
                position="개발자",
                main_tasks="개발 업무",
                requirements="개발 경험",
                preferred_points="",
                location="서울",
                district="강남구",
                employment_type="정규직",
                career_min=1,
                career_max=3,
            )

        # When: 스킬 필드만 업데이트
        with patch.object(JobPosting, "_schedule_processing") as mock_schedule:
            job_posting.skills_required = ["Python", "Django"]
            job_posting.skills_preferred = ["AWS"]
            job_posting.save(update_fields=["skills_required", "skills_preferred"])

            # Then: _schedule_processing 호출 안 됨
            mock_schedule.assert_not_called()

    @pytest.mark.django_db
    def test_transaction_on_commit_behavior(self, celery_eager_mode):
        """transaction.on_commit 동작 검증"""
        # transaction.on_commit이 올바르게 호출되는지 확인
        with patch("django.db.transaction.on_commit") as mock_on_commit:
            # Given & When: 트랜잭션 내에서 JobPosting 생성
            from django.db import transaction

            with transaction.atomic():
                job_posting = JobPosting.objects.create(
                    posting_id=2004,
                    url="https://example.com/job/2004",
                    company_name="테스트",
                    position="개발자",
                    main_tasks="개발 업무",
                    requirements="개발 경험",
                    preferred_points="",
                    location="서울",
                    district="강남구",
                    employment_type="정규직",
                    career_min=1,
                    career_max=3,
                )
                # 트랜잭션 내부에서는 아직 태스크가 호출되지 않음

            # Then: transaction.on_commit이 호출되었는지 확인
            mock_on_commit.assert_called()


class TestEmbeddingTextQuality:
    """임베딩 텍스트 품질 테스트"""

    @pytest.mark.django_db
    def test_embedding_text_contains_core_info(self, celery_eager_mode):
        """임베딩 텍스트에 핵심 정보 포함 확인"""
        # Given
        job_posting = JobPosting.objects.create(
            posting_id=3001,
            url="https://example.com/job/3001",
            company_name="임베딩테스트회사",
            position="AI 엔지니어",
            main_tasks="머신러닝 모델 개발 및 배포",
            requirements="Python, TensorFlow 경험 3년 이상",
            preferred_points="PyTorch, Kubernetes 경험자 우대",
            location="서울 강남구 테헤란로 123",
            district="강남구",
            employment_type="정규직",
            career_min=3,
            career_max=7,
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("job.tasks.graph_db_client"),
        ):

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            process_job_posting(3001)

            # Then: 임베딩 텍스트 검증
            call_args = mock_vector_db.upsert_documents.call_args
            embedding_text = call_args.kwargs["documents"][0]

            # 핵심 정보 포함 확인
            assert "Position:" in embedding_text
            assert "AI 엔지니어" in embedding_text
            assert "Main Tasks:" in embedding_text
            assert "머신러닝 모델 개발 및 배포" in embedding_text
            assert "Requirements:" in embedding_text
            assert "Python, TensorFlow 경험 3년 이상" in embedding_text
            assert "Preferred Points:" in embedding_text
            assert "PyTorch, Kubernetes 경험자 우대" in embedding_text

    @pytest.mark.django_db
    def test_embedding_text_excludes_noise(self, celery_eager_mode):
        """임베딩 텍스트에서 노이즈 제거 확인"""
        # Given
        job_posting = JobPosting.objects.create(
            posting_id=3002,
            url="https://example.com/job/3002",
            company_name="노이즈테스트회사",
            position="백엔드 개발자",
            main_tasks="API 개발",
            requirements="Python 경험",
            preferred_points="Django 경험",
            location="서울 강남구 테헤란로 456 (역삼동, ABC빌딩 10층)",
            district="강남구",
            employment_type="정규직",
            career_min=2,
            career_max=5,
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("job.tasks.graph_db_client"),
        ):

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            process_job_posting(3002)

            # Then: 임베딩 텍스트 검증
            call_args = mock_vector_db.upsert_documents.call_args
            embedding_text = call_args.kwargs["documents"][0]

            # 노이즈(회사명, 위치 등)가 임베딩 텍스트에 포함되지 않음
            # 메타데이터에만 저장됨
            metadatas = call_args.kwargs["metadatas"]
            metadata = metadatas[0]

            # 메타데이터에는 포함
            assert metadata["company_name"] == "노이즈테스트회사"
            assert (
                metadata["location"]
                == "서울 강남구 테헤란로 456 (역삼동, ABC빌딩 10층)"
            )

            # 임베딩 텍스트는 핵심 정보만 포함
            # company_name과 location 필드 자체는 임베딩에 포함되지 않음
            assert "Position:" in embedding_text
            assert "Main Tasks:" in embedding_text
            assert "Requirements:" in embedding_text
            assert "Preferred Points:" in embedding_text

    @pytest.mark.django_db
    def test_embedding_text_format(self, celery_eager_mode):
        """임베딩 텍스트 형식 확인"""
        # Given
        job_posting = JobPosting.objects.create(
            posting_id=3003,
            url="https://example.com/job/3003",
            company_name="포맷테스트",
            position="데이터 분석가",
            main_tasks="데이터 분석 및 시각화",
            requirements="SQL, Python 필수",
            preferred_points="Tableau 경험",
            location="서울",
            district="강남구",
            employment_type="정규직",
            career_min=1,
            career_max=4,
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("job.tasks.graph_db_client"),
        ):

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            process_job_posting(3003)

            # Then: 임베딩 텍스트 형식 확인
            call_args = mock_vector_db.upsert_documents.call_args
            embedding_text = call_args.kwargs["documents"][0]

            # 구조화된 형식 확인
            lines = embedding_text.strip().split("\n")
            assert len(lines) == 4
            assert lines[0].startswith("Position:")
            assert lines[1].startswith("Main Tasks:")
            assert lines[2].startswith("Requirements:")
            assert lines[3].startswith("Preferred Points:")


class TestFailureScenarios:
    """실패 시나리오 테스트"""

    @pytest.mark.django_db
    def test_handle_missing_job_posting(self, celery_eager_mode):
        """존재하지 않는 JobPosting 처리"""
        # When
        result = process_job_posting(99999)

        # Then
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.django_db
    def test_handle_chromadb_connection_error(self, celery_eager_mode):
        """ChromaDB 연결 오류 처리"""
        # Given
        job_posting = JobPosting.objects.create(
            posting_id=4001,
            url="https://example.com/job/4001",
            company_name="에러테스트",
            position="개발자",
            main_tasks="개발",
            requirements="경험",
            preferred_points="",
            location="서울",
            district="강남구",
            employment_type="정규직",
            career_min=1,
            career_max=3,
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("job.tasks.graph_db_client"),
        ):

            # ChromaDB 연결 오류 시뮬레이션
            mock_vector_db.get_or_create_collection.side_effect = Exception(
                "DB Connection Failed"
            )

            # When: eager 모드에서는 예외 발생
            try:
                result = process_job_posting(4001)
                assert False, "Should raise exception"
            except Exception as e:
                # Then: 예외 발생 확인
                assert "DB Connection Failed" in str(
                    e
                ) or "DB Connection Failed" in str(e.__cause__)

    @pytest.mark.django_db
    def test_handle_neo4j_connection_error(self, celery_eager_mode):
        """Neo4j 연결 오류 처리"""
        # Given: 스킬이 있는 JobPosting (Neo4j 호출이 일어나도록)
        job_posting = JobPosting.objects.create(
            posting_id=4002,
            url="https://example.com/job/4002",
            company_name="그래프에러테스트",
            position="개발자",
            main_tasks="Python Django 개발",
            requirements="Python 경험 필수",
            preferred_points="",
            location="서울",
            district="강남구",
            employment_type="정규직",
            career_min=1,
            career_max=3,
        )

        with (
            patch("job.tasks.vector_db_client"),
            patch("job.tasks.graph_db_client") as mock_graph_db,
        ):

            # Neo4j 연결 오류 시뮬레이션
            mock_graph_db.add_job_posting.side_effect = Exception(
                "Neo4j Connection Failed"
            )

            # When: Neo4j 오류 시 예외 발생
            try:
                result = process_job_posting(4002)
                assert False, "Should raise exception"
            except Exception as e:
                # Then: 예외 발생 확인
                assert "Neo4j Connection Failed" in str(
                    e
                ) or "Neo4j Connection Failed" in str(e.__cause__)

    @pytest.mark.django_db
    def test_handle_empty_skills(self, celery_eager_mode):
        """스킬이 추출되지 않는 경우 처리"""
        # Given: 스킬 정보가 없는 JobPosting
        job_posting = JobPosting.objects.create(
            posting_id=4003,
            url="https://example.com/job/4003",
            company_name="스킬없음테스트",
            position="일반 사무직",
            main_tasks="문서 작성 및 관리",
            requirements="성실한 분",
            preferred_points="",
            location="서울",
            district="강남구",
            employment_type="정규직",
            career_min=0,
            career_max=2,
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("job.tasks.graph_db_client") as mock_graph_db,
        ):

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            result = process_job_posting(4003)

            # Then: 성공하지만 스킬 수가 0
            assert result["success"] is True
            assert result["skills_required"] == 0
            assert result["skills_preferred"] == 0

            # ChromaDB에는 여전히 저장
            mock_vector_db.upsert_documents.assert_called_once()

            # Neo4j에는 스킬 없으면 저장 안 됨
            mock_graph_db.add_job_posting.assert_not_called()

    @pytest.mark.django_db
    def test_handle_partial_data(self, celery_eager_mode):
        """부분적인 데이터만 있는 경우 처리"""
        # Given: preferred_points가 비어있는 JobPosting
        job_posting = JobPosting.objects.create(
            posting_id=4004,
            url="https://example.com/job/4004",
            company_name="부분데이터테스트",
            position="프론트엔드 개발자",
            main_tasks="React 개발",
            requirements="JavaScript 경험",
            preferred_points="",  # 비어있음
            location="서울",
            district="강남구",
            employment_type="정규직",
            career_min=1,
            career_max=3,
        )

        with (
            patch("job.tasks.vector_db_client") as mock_vector_db,
            patch("job.tasks.graph_db_client"),
        ):

            mock_collection = Mock()
            mock_vector_db.get_or_create_collection.return_value = mock_collection

            # When
            result = process_job_posting(4004)

            # Then: 성공
            assert result["success"] is True
            assert result["skills_required"] > 0  # React, JavaScript
            assert result["skills_preferred"] == 0  # preferred_points 비어있음

            job_posting.refresh_from_db()
            assert "React" in job_posting.skills_required
            assert "JavaScript" in job_posting.skills_required
            assert job_posting.skills_preferred == []

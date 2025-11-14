import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from agent.tools import vector_search_job_postings_tool
from django.test import Client, TestCase
from job.models import JobPosting
from job.signals import SKILL_LIST, _extract_career_years_regex, _extract_resume_details


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


class TestResumeAnalysis(TestCase):
    """이력서 분석 함수 테스트"""

    def test_extract_career_years_regex_korean(self):
        """한국어 경력 연차 추출 테스트"""
        test_cases = [
            ("경력: 5년", 5),
            ("3년 경력의 백엔드 개발자입니다.", 3),
            ("총 7년의 개발 경험이 있습니다.", 7),
            ("경력이 없습니다.", 0),
        ]

        for resume_text, expected_years in test_cases:
            with self.subTest(text=resume_text):
                result = _extract_career_years_regex(resume_text)
                self.assertEqual(result, expected_years)

    def test_extract_career_years_regex_english(self):
        """영어 경력 연차 추출 테스트"""
        test_cases = [
            ("5 years of experience in backend development", 5),
            ("3+ years experience with Python", 3),
            ("I am a developer with 7 years experience", 7),
        ]

        for resume_text, expected_years in test_cases:
            with self.subTest(text=resume_text):
                result = _extract_career_years_regex(resume_text)
                self.assertEqual(result, expected_years)

    @patch("job.signals.genai.Client")
    def test_extract_resume_details_with_llm_success(self, mock_genai_client):
        """LLM을 사용한 이력서 분석 성공 테스트"""
        # Mock LLM 응답
        mock_response = Mock()
        mock_response.text = json.dumps(
            {"career_years": 5, "strengths": "백엔드 개발 및 대용량 트래픽 처리 경험"}
        )

        mock_client_instance = Mock()
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_genai_client.return_value = mock_client_instance

        # 테스트 이력서
        resume_content = """
        저는 5년 경력의 백엔드 개발자입니다.
        Python, Django, FastAPI를 사용하여 대용량 트래픽을 처리하는
        서비스를 개발한 경험이 있습니다.
        AWS와 Docker를 활용한 배포 경험도 풍부합니다.
        """

        result = _extract_resume_details(resume_content, SKILL_LIST)

        # 검증
        self.assertIn("Python", result["skills"])
        self.assertIn("Django", result["skills"])
        self.assertIn("FastAPI", result["skills"])
        self.assertIn("AWS", result["skills"])
        self.assertIn("Docker", result["skills"])
        self.assertEqual(result["career_years"], 5)
        self.assertEqual(result["strengths"], "백엔드 개발 및 대용량 트래픽 처리 경험")

    @patch("job.signals.genai.Client")
    def test_extract_resume_details_llm_failure_fallback(self, mock_genai_client):
        """LLM 실패 시 Fallback 테스트"""
        # LLM 호출 실패 시뮬레이션
        mock_genai_client.side_effect = Exception("API Error")

        resume_content = "5년 경력의 Python, Django 개발자입니다."

        result = _extract_resume_details(resume_content, SKILL_LIST)

        # Fallback으로 정규표현식 사용
        self.assertEqual(result["career_years"], 5)
        self.assertIn("Python", result["skills"])
        self.assertIn("Django", result["skills"])
        self.assertIn("자동 분석", result["strengths"])

    @patch.dict("os.environ", {}, clear=True)
    def test_extract_resume_details_no_api_key(self):
        """API 키 없을 때 Fallback 테스트"""
        resume_content = "3년 경력의 React, JavaScript 개발자입니다."

        result = _extract_resume_details(resume_content, SKILL_LIST)

        # API 키가 없으면 정규표현식 사용
        self.assertEqual(result["career_years"], 3)
        self.assertIn("React", result["skills"])
        self.assertIn("JavaScript", result["skills"])
        self.assertEqual(result["strengths"], "API 키 미설정으로 분석 불가")


@pytest.mark.django_db
class TestJobPostingSignals(TestCase):
    @patch("job.signals.graph_db_client")
    @patch("job.signals.vector_db_client")
    def test_embed_job_posting_on_save(
        self, mock_vector_db_client, mock_graph_db_client
    ):
        """
        JobPosting 저장 시 벡터 DB와 그래프 DB에 모두 저장되는지 테스트
        """
        # --- Vector DB Mock ---
        mock_collection = MagicMock()
        mock_vector_db_client.get_or_create_collection.return_value = mock_collection

        # --- JobPosting 생성 (post_save 시그널 발생) ---
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

        # --- Vector DB Assertions ---
        # Note: 시그널 내에서 skills 업데이트 시 save()가 다시 호출되어 2번 호출됨
        self.assertGreaterEqual(
            mock_vector_db_client.get_or_create_collection.call_count, 1
        )
        mock_vector_db_client.get_or_create_collection.assert_called_with(
            "job_postings"
        )
        self.assertGreaterEqual(mock_vector_db_client.upsert_documents.call_count, 1)
        _, call_kwargs = mock_vector_db_client.upsert_documents.call_args
        self.assertEqual(call_kwargs["ids"], [str(job_posting.posting_id)])

        # --- Graph DB Assertions ---
        self.assertGreaterEqual(mock_graph_db_client.add_job_posting.call_count, 1)
        _, call_kwargs = mock_graph_db_client.add_job_posting.call_args
        self.assertEqual(call_kwargs["posting_id"], 123)
        self.assertEqual(call_kwargs["company_name"], "Test Corp")
        # 스킬 추출이 올바르게 되었는지 확인 (대소문자, 순서 무관)
        self.assertSetEqual(
            set(call_kwargs["skills"]), {"Python", "Django", "FastAPI", "AWS"}
        )


@pytest.mark.django_db
class TestAgentTools(TestCase):
    @patch("agent.tools.vector_db_client")
    def test_vector_search_job_postings_tool(self, mock_vector_db_client):
        """
        vector_search_job_postings_tool이 벡터 DB 검색 결과를 사용하여
        올바르게 JobPosting 객체를 조회하는지 테스트
        """
        # 테스트 데이터 생성
        create_test_job_posting(
            posting_id=101, position="Backend Developer", company_name="A"
        )
        create_test_job_posting(
            posting_id=102, position="Frontend Developer", company_name="B"
        )

        # Mock setup
        mock_query_result = {"ids": [["102", "101"]]}
        mock_vector_db_client.query.return_value = mock_query_result

        # 툴 호출
        result_json = vector_search_job_postings_tool.run(
            query_text="frontend developer", n_results=2
        )
        result_data = json.loads(result_json)

        # Assertions
        self.assertEqual(len(result_data), 2)
        self.assertEqual(result_data[0]["posting_id"], 102)
        self.assertEqual(result_data[1]["posting_id"], 101)


@pytest.mark.django_db
class TestJobViews(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("job.views.vector_search_job_postings_tool")
    def test_job_search_view(self, mock_search_tool):
        """
        JobSearchView가 검색 쿼리를 받아 툴을 호출하고 결과를 반환하는지 테스트
        """
        # Mock setup
        mock_result = [{"id": 1, "title": "Awesome Job"}]
        mock_search_tool.run.return_value = json.dumps(mock_result)

        # 정상 호출 테스트
        response = self.client.get("/api/v1/search/?query=python")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mock_result)
        mock_search_tool.run.assert_called_once_with(query_text="python")

        # 쿼리 파라미터가 없는 경우 테스트
        response = self.client.get("/api/v1/search/")
        self.assertEqual(response.status_code, 400)

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

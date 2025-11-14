import json
from unittest.mock import MagicMock, patch

import pytest
from agent.tools import vector_search_job_postings_tool
from django.test import Client, TestCase
from job.models import JobPosting


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
        mock_vector_db_client.get_or_create_collection.assert_called_once_with(
            "job_postings"
        )
        mock_vector_db_client.upsert_documents.assert_called_once()
        _, call_kwargs = mock_vector_db_client.upsert_documents.call_args
        self.assertEqual(call_kwargs["ids"], [str(job_posting.posting_id)])

        # --- Graph DB Assertions ---
        mock_graph_db_client.add_job_posting.assert_called_once()
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

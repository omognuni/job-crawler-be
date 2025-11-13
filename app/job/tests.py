import json
from unittest.mock import MagicMock, patch

import pytest
from agent.tools import vector_search_job_postings_tool
from django.test import TestCase
from job.models import JobPosting


@pytest.mark.django_db
class TestJobPostingSignals(TestCase):
    @patch("job.signals.vector_db_client")
    def test_embed_job_posting_on_save(self, mock_vector_db_client):
        """
        JobPosting이 저장될 때 시그널 핸들러가 호출되고,
        벡터 DB 클라이언트의 upsert_documents가 올바른 인자와 함께 호출되는지 테스트
        """
        # Mock setup
        mock_collection = MagicMock()
        mock_vector_db_client.get_or_create_collection.return_value = mock_collection

        # JobPosting 생성 (이때 post_save 시그널이 발생해야 함)
        job_posting = JobPosting.objects.create(
            posting_id=123,
            url="http://example.com",
            company_name="Test Corp",
            position="Software Engineer",
            main_tasks="Develop amazing things.",
            requirements="Python, Django",
            preferred_points="FastAPI, AWS",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=1,
            career_max=5,
        )

        # Assertions
        mock_vector_db_client.get_or_create_collection.assert_called_once_with(
            "job_postings"
        )

        expected_document = f"""
    Position: {job_posting.position}
    Main Tasks: {job_posting.main_tasks}
    Requirements: {job_posting.requirements}
    Preferred Points: {job_posting.preferred_points}
    """
        mock_vector_db_client.upsert_documents.assert_called_once()
        call_args, call_kwargs = mock_vector_db_client.upsert_documents.call_args

        self.assertEqual(call_kwargs["collection"], mock_collection)
        self.assertEqual(call_kwargs["documents"], [expected_document])
        self.assertEqual(call_kwargs["ids"], [str(job_posting.posting_id)])
        self.assertIn("company_name", call_kwargs["metadatas"][0])


@pytest.mark.django_db
class TestAgentTools(TestCase):
    @patch("agent.tools.vector_db_client")
    def test_vector_search_job_postings_tool(self, mock_vector_db_client):
        """
        vector_search_job_postings_tool이 벡터 DB 검색 결과를 사용하여
        올바르게 JobPosting 객체를 조회하는지 테스트
        """
        # 테스트 데이터 생성
        jp1 = JobPosting.objects.create(
            posting_id=101,
            position="Backend Developer",
            company_name="A",
            career_min=0,
            career_max=0,
        )
        jp2 = JobPosting.objects.create(
            posting_id=102,
            position="Frontend Developer",
            company_name="B",
            career_min=0,
            career_max=0,
        )
        jp3 = JobPosting.objects.create(
            posting_id=103,
            position="Data Scientist",
            company_name="C",
            career_min=0,
            career_max=0,
        )

        # Mock setup
        mock_query_result = {
            "ids": [["102", "101"]]
        }  # 순서가 다르게 반환되는 경우 테스트
        mock_vector_db_client.query.return_value = mock_query_result

        # 툴 호출
        query_text = "frontend developer with react"

        result_json = vector_search_job_postings_tool.run(
            query_text=query_text, n_results=2
        )
        result_data = json.loads(result_json)

        # Assertions
        mock_vector_db_client.query.assert_called_once_with(
            collection=mock_vector_db_client.get_or_create_collection.return_value,
            query_texts=[query_text],
            n_results=2,
        )

        # 결과 개수 확인
        self.assertEqual(len(result_data), 2)
        # 벡터 DB가 반환한 ID 순서대로 결과가 정렬되었는지 확인
        self.assertEqual(result_data[0]["posting_id"], 102)
        self.assertEqual(result_data[1]["posting_id"], 101)
        self.assertEqual(result_data[0]["company_name"], "B")
        self.assertEqual(result_data[1]["company_name"], "A")

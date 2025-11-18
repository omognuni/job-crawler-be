"""
Tests for process_data management command.
"""

from io import StringIO
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.core.management import call_command
from job.models import JobPosting, Resume


@pytest.mark.django_db
class TestProcessDataCommand:
    """Tests for process_data management command."""

    def test_no_arguments_shows_warning(self):
        """
        커맨드를 인자 없이 실행하면 경고 메시지를 출력해야 함
        """
        out = StringIO()
        call_command("process_data", stdout=out)
        output = out.getvalue()
        assert "Please specify a model to process" in output

    def test_process_job_postings_flag(self):
        """
        --model jobposting 플래그로 JobPosting 처리가 트리거되어야 함
        """
        # Create test data
        JobPosting.objects.create(
            posting_id=1,
            company_name="Test Company",
            position="Backend Developer",
            url="https://example.com/job/1",
            main_tasks="Task 1",
            requirements="Req 1",
            preferred_points="Pref 1",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=0,
            career_max=3,
        )
        JobPosting.objects.create(
            posting_id=2,
            company_name="Another Company",
            position="Frontend Developer",
            url="https://example.com/job/2",
            main_tasks="Task 2",
            requirements="Req 2",
            preferred_points="Pref 2",
            location="Busan",
            district="Haeundae",
            employment_type="Full-time",
            career_min=1,
            career_max=5,
        )

        # Mock group to avoid actual Celery calls
        mock_result = Mock()
        with patch("job.management.commands.process_data.group") as mock_group:
            mock_group.return_value.apply_async.return_value = mock_result

            out = StringIO()
            call_command("process_data", "--model", "jobposting", stdout=out)
            output = out.getvalue()

            # Verify output
            assert "Fetching JobPostings" in output
            assert "Submitting 2 JobPosting tasks" in output
            assert "Successfully submitted 2 JobPosting tasks" in output

            # Verify group was called once (single batch for 2 items)
            mock_group.assert_called_once()
            mock_group.return_value.apply_async.assert_called_once()

    def test_process_resumes_flag(self):
        """
        --model resume 플래그로 Resume 처리가 트리거되어야 함
        """
        # Create test data
        Resume.objects.create(user_id=101, content="Resume 1")
        Resume.objects.create(user_id=102, content="Resume 2")
        Resume.objects.create(user_id=103, content="Resume 3")

        # Mock group to avoid actual Celery calls
        mock_result = Mock()
        with patch("job.management.commands.process_data.group") as mock_group:
            mock_group.return_value.apply_async.return_value = mock_result

            out = StringIO()
            call_command("process_data", "--model", "resume", stdout=out)
            output = out.getvalue()

            # Verify output
            assert "Fetching Resumes" in output
            assert "Submitting 3 Resume tasks" in output
            assert "Successfully submitted 3 Resume tasks" in output

            # Verify group was called once (single batch for 3 items)
            mock_group.assert_called_once()
            mock_group.return_value.apply_async.assert_called_once()

    def test_process_all_flag(self):
        """
        --all 플래그로 모든 모델이 처리되어야 함
        """
        # Create test data
        JobPosting.objects.create(
            posting_id=1,
            company_name="Test Company",
            position="Developer",
            url="https://example.com/job/1",
            main_tasks="Task",
            requirements="Req",
            preferred_points="Pref",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=0,
            career_max=5,
        )
        Resume.objects.create(user_id=101, content="Resume 1")

        # Mock group to avoid actual Celery calls
        mock_result = Mock()
        with patch("job.management.commands.process_data.group") as mock_group:
            mock_group.return_value.apply_async.return_value = mock_result

            out = StringIO()
            call_command("process_data", "--all", stdout=out)
            output = out.getvalue()

            # Verify both models were processed
            assert "JobPosting" in output
            assert "Resume" in output
            assert "Finished submitting all tasks to Celery" in output

            # Verify group was called twice (once for JobPostings, once for Resumes)
            assert mock_group.call_count == 2
            assert mock_group.return_value.apply_async.call_count == 2

    def test_batch_size_parameter(self):
        """
        --batch-size 파라미터가 배치 크기를 올바르게 설정해야 함
        """
        # Create 5 job postings
        for i in range(1, 6):
            JobPosting.objects.create(
                posting_id=i,
                company_name=f"Company {i}",
                position=f"Position {i}",
                url=f"https://example.com/job/{i}",
                main_tasks="Task",
                requirements="Req",
                preferred_points="Pref",
                location="Seoul",
                district="Gangnam",
                employment_type="Full-time",
                career_min=0,
                career_max=5,
            )

        # Mock group to avoid actual Celery calls
        mock_result = Mock()
        with patch("job.management.commands.process_data.group") as mock_group:
            mock_group.return_value.apply_async.return_value = mock_result

            out = StringIO()
            call_command(
                "process_data", "--model", "jobposting", "--batch-size", "2", stdout=out
            )
            output = out.getvalue()

            # Should process 5 items in 3 batches (2, 2, 1)
            assert "batch 1" in output.lower()
            assert "batch 2" in output.lower()
            assert "batch 3" in output.lower()

            # Verify group was called 3 times (3 batches)
            assert mock_group.call_count == 3

    def test_wait_parameter(self):
        """
        --wait 파라미터가 배치 완료를 대기해야 함
        """
        JobPosting.objects.create(
            posting_id=1,
            company_name="Test Company",
            position="Developer",
            url="https://example.com/job/1",
            main_tasks="Task",
            requirements="Req",
            preferred_points="Pref",
            location="Seoul",
            district="Gangnam",
            employment_type="Full-time",
            career_min=0,
            career_max=5,
        )

        # Mock group to avoid actual Celery calls
        mock_result = Mock()
        mock_result.get = Mock(return_value=None)
        with patch("job.management.commands.process_data.group") as mock_group:
            mock_group.return_value.apply_async.return_value = mock_result

            out = StringIO()
            call_command("process_data", "--model", "jobposting", "--wait", stdout=out)
            output = out.getvalue()

            # Verify get() was called to wait for completion
            mock_result.get.assert_called_once_with(timeout=600)
            assert "Completed batch" in output

    def test_empty_queryset_jobposting(self):
        """
        JobPosting이 없을 때 경고 메시지를 출력해야 함
        """
        out = StringIO()
        call_command("process_data", "--model", "jobposting", stdout=out)
        output = out.getvalue()

        assert "No JobPostings found" in output

    def test_empty_queryset_resume(self):
        """
        Resume이 없을 때 경고 메시지를 출력해야 함
        """
        out = StringIO()
        call_command("process_data", "--model", "resume", stdout=out)
        output = out.getvalue()

        assert "No Resumes found" in output

    def test_large_batch_processing(self):
        """
        많은 양의 데이터를 올바른 배치 크기로 처리해야 함
        """
        # Create 250 job postings
        for i in range(1, 251):
            JobPosting.objects.create(
                posting_id=i,
                company_name=f"Company {i}",
                position=f"Position {i}",
                url=f"https://example.com/job/{i}",
                main_tasks="Task",
                requirements="Req",
                preferred_points="Pref",
                location="Seoul",
                district="Gangnam",
                employment_type="Full-time",
                career_min=0,
                career_max=5,
            )

        # Mock group to avoid actual Celery calls
        mock_result = Mock()
        with patch("job.management.commands.process_data.group") as mock_group:
            mock_group.return_value.apply_async.return_value = mock_result

            out = StringIO()
            # Default batch size is 100, so 250 items = 3 batches
            call_command("process_data", "--model", "jobposting", stdout=out)
            output = out.getvalue()

            # Verify batch processing
            assert "Submitting 250 JobPosting tasks" in output
            assert "Successfully submitted 250 JobPosting tasks" in output

            # Should have 3 batches with default batch_size=100
            assert mock_group.call_count == 3

    def test_resume_timeout_is_longer(self):
        """
        Resume 처리는 LLM 호출 때문에 더 긴 타임아웃을 사용해야 함
        """
        Resume.objects.create(user_id=101, content="Resume 1")

        # Mock group to avoid actual Celery calls
        mock_result = Mock()
        mock_result.get = Mock(return_value=None)
        with patch("job.management.commands.process_data.group") as mock_group:
            mock_group.return_value.apply_async.return_value = mock_result

            out = StringIO()
            call_command("process_data", "--model", "resume", "--wait", stdout=out)

            # Verify longer timeout for resumes (1200 seconds = 20 minutes)
            mock_result.get.assert_called_once_with(timeout=1200)

    def test_command_output_formatting(self):
        """
        커맨드 출력 포맷이 올바르게 표시되어야 함
        """
        for i in range(1, 4):
            JobPosting.objects.create(
                posting_id=i,
                company_name=f"Company {i}",
                position=f"Position {i}",
                url=f"https://example.com/job/{i}",
                main_tasks="Task",
                requirements="Req",
                preferred_points="Pref",
                location="Seoul",
                district="Gangnam",
                employment_type="Full-time",
                career_min=0,
                career_max=5,
            )

        # Mock group to avoid actual Celery calls
        mock_result = Mock()
        with patch("job.management.commands.process_data.group") as mock_group:
            mock_group.return_value.apply_async.return_value = mock_result

            out = StringIO()
            call_command("process_data", "--model", "jobposting", stdout=out)
            output = out.getvalue()

            # Check for proper formatting
            assert "Fetching JobPostings..." in output
            assert "Submitting 3 JobPosting tasks to Celery queue..." in output
            assert "Submitted batch 1: 3/3 tasks" in output
            assert "Successfully submitted 3 JobPosting tasks" in output
            assert "Check Celery worker logs for progress" in output
            assert "Finished submitting all tasks to Celery" in output

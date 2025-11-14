"""
run_agent.py의 에러 처리 개선 테스트
"""

import json
from unittest.mock import Mock, patch

import pytest
from django.test import TestCase
from run_agent import main, send_slack_message


class TestRunAgent(TestCase):
    """run_agent.py 테스트"""

    @patch("run_agent.settings")
    @patch("run_agent.requests.post")
    def test_send_slack_message_success(self, mock_post, mock_settings):
        """Slack 메시지 전송 성공 테스트"""
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = send_slack_message("테스트 메시지")

        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch("run_agent.settings")
    def test_send_slack_message_no_webhook(self, mock_settings):
        """SLACK_WEBHOOK_URL이 없을 때 테스트"""
        mock_settings.SLACK_WEBHOOK_URL = None

        result = send_slack_message("테스트 메시지")

        self.assertFalse(result)

    @patch("run_agent.settings")
    @patch("run_agent.requests.post")
    def test_send_slack_message_failure(self, mock_post, mock_settings):
        """Slack 메시지 전송 실패 테스트"""
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"
        mock_post.side_effect = Exception("Network error")

        result = send_slack_message("테스트 메시지")

        self.assertFalse(result)

    @patch("run_agent.send_slack_message")
    @patch("run_agent.Resume")
    @patch("run_agent.settings")
    def test_main_no_resumes(self, mock_settings, mock_resume, mock_send_slack):
        """이력서가 없을 때 테스트"""
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"
        mock_resume.objects.all.return_value.exists.return_value = False

        main()

        mock_send_slack.assert_called_once()
        call_args = mock_send_slack.call_args[0][0]
        self.assertIn("이력서가 없습니다", call_args)

    @patch("run_agent.send_slack_message")
    @patch("run_agent.JobHunterCrew")
    @patch("run_agent.Resume")
    @patch("run_agent.settings")
    def test_main_result_is_none(
        self, mock_settings, mock_resume, mock_crew_class, mock_send_slack
    ):
        """Agent 결과가 None일 때 테스트"""
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

        # Mock Resume
        mock_resume_obj = Mock()
        mock_resume_obj.user_id = 1

        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([mock_resume_obj]))
        mock_resume.objects.all.return_value = mock_queryset

        # Mock Crew - returns None
        mock_crew_instance = Mock()
        mock_crew_instance.run.return_value = None
        mock_crew_class.return_value = mock_crew_instance

        main()

        # Slack 메시지가 전송되었는지 확인
        self.assertTrue(mock_send_slack.called)
        error_calls = [
            call for call in mock_send_slack.call_args_list if "None" in str(call)
        ]
        self.assertTrue(len(error_calls) > 0)

    @patch("run_agent.send_slack_message")
    @patch("run_agent.JobHunterCrew")
    @patch("run_agent.Resume")
    @patch("run_agent.settings")
    def test_main_result_json_dict_is_none(
        self, mock_settings, mock_resume, mock_crew_class, mock_send_slack
    ):
        """result.json_dict가 None일 때 테스트 (원래 버그 상황)"""
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

        # Mock Resume
        mock_resume_obj = Mock()
        mock_resume_obj.user_id = 1

        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([mock_resume_obj]))
        mock_resume.objects.all.return_value = mock_queryset

        # Mock Crew - json_dict is None
        mock_result = Mock()
        mock_result.json_dict = None
        mock_result.raw = "Some raw output"

        mock_crew_instance = Mock()
        mock_crew_instance.run.return_value = mock_result
        mock_crew_class.return_value = mock_crew_instance

        # 이제 에러가 발생하지 않아야 함
        main()

        # Slack 메시지가 전송되었는지 확인
        self.assertTrue(mock_send_slack.called)

    @patch("run_agent.send_slack_message")
    @patch("run_agent.JobHunterCrew")
    @patch("run_agent.Resume")
    @patch("run_agent.settings")
    def test_main_success(
        self, mock_settings, mock_resume, mock_crew_class, mock_send_slack
    ):
        """정상 실행 테스트"""
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

        # Mock Resume
        mock_resume_obj = Mock()
        mock_resume_obj.user_id = 1

        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([mock_resume_obj]))
        mock_resume.objects.all.return_value = mock_queryset

        # Mock Crew - 정상 결과
        mock_result = Mock()
        mock_result.json_dict = {
            "status": "success",
            "user_id": 1,
            "saved_count": 2,
            "recommendations": [
                {
                    "rank": 1,
                    "company_name": "테스트 회사",
                    "position": "백엔드 개발자",
                    "url": "https://example.com/job/1",
                    "match_score": 95,
                },
                {
                    "rank": 2,
                    "company_name": "테스트 회사2",
                    "position": "풀스택 개발자",
                    "url": "https://example.com/job/2",
                    "match_score": 90,
                },
            ],
        }

        mock_crew_instance = Mock()
        mock_crew_instance.run.return_value = mock_result
        mock_crew_class.return_value = mock_crew_instance

        main()

        # Slack 메시지가 전송되었는지 확인
        self.assertTrue(mock_send_slack.called)
        success_call = mock_send_slack.call_args_list[-1][0][0]
        self.assertIn("테스트 회사", success_call)
        self.assertIn("백엔드 개발자", success_call)

    @patch("run_agent.send_slack_message")
    @patch("run_agent.JobHunterCrew")
    @patch("run_agent.Resume")
    @patch("run_agent.settings")
    def test_main_empty_recommendations(
        self, mock_settings, mock_resume, mock_crew_class, mock_send_slack
    ):
        """추천 결과가 비어있을 때 테스트"""
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

        # Mock Resume
        mock_resume_obj = Mock()
        mock_resume_obj.user_id = 1

        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([mock_resume_obj]))
        mock_resume.objects.all.return_value = mock_queryset

        # Mock Crew - 빈 추천
        mock_result = Mock()
        mock_result.json_dict = {
            "status": "success",
            "user_id": 1,
            "saved_count": 0,
            "recommendations": [],
        }

        mock_crew_instance = Mock()
        mock_crew_instance.run.return_value = mock_result
        mock_crew_class.return_value = mock_crew_instance

        main()

        # 경고 메시지가 전송되었는지 확인
        self.assertTrue(mock_send_slack.called)
        warning_call = mock_send_slack.call_args_list[-1][0][0]
        self.assertIn("추천할 채용 공고가 없습니다", warning_call)

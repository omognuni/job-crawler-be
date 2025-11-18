"""
run_agent.py 테스트 - AI-Free 추천 엔진 버전
"""

import json
from unittest.mock import MagicMock, Mock, patch

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
    @patch("run_agent.get_recommendations")
    @patch("run_agent.Resume")
    @patch("run_agent.settings")
    def test_main_no_recommendations(
        self, mock_settings, mock_resume, mock_get_recommendations, mock_send_slack
    ):
        """추천 결과가 없을 때 테스트"""
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

        # Mock Resume
        mock_resume_obj = Mock()
        mock_resume_obj.user_id = 1

        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([mock_resume_obj]))
        mock_resume.objects.all.return_value = mock_queryset

        # Mock get_recommendations - 빈 리스트 반환
        mock_get_recommendations.return_value = []

        main()

        # 경고 메시지가 전송되었는지 확인
        self.assertTrue(mock_send_slack.called)
        warning_calls = [
            call
            for call in mock_send_slack.call_args_list
            if "추천 결과가 없습니다" in str(call)
        ]
        self.assertTrue(len(warning_calls) > 0)

    @patch("run_agent.send_slack_message")
    @patch("run_agent.JobRecommendation")
    @patch("run_agent.get_recommendations")
    @patch("run_agent.Resume")
    @patch("run_agent.settings")
    def test_main_success(
        self,
        mock_settings,
        mock_resume,
        mock_get_recommendations,
        mock_job_recommendation,
        mock_send_slack,
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

        # Mock get_recommendations - 정상 결과
        mock_get_recommendations.return_value = [
            {
                "posting_id": 1001,
                "company_name": "테스트 회사",
                "position": "백엔드 개발자",
                "url": "https://example.com/job/1",
                "match_score": 85,
                "match_reason": "필수 스킬 5/6개 보유 | 경력 요건 충족 (3년)",
            },
            {
                "posting_id": 1002,
                "company_name": "테스트 회사2",
                "position": "풀스택 개발자",
                "url": "https://example.com/job/2",
                "match_score": 78,
                "match_reason": "필수 스킬 4/5개 보유 | 우대사항 2개 충족",
            },
        ]

        # Mock JobRecommendation.objects.update_or_create
        mock_recommendation = Mock()
        mock_job_recommendation.objects.update_or_create.return_value = (
            mock_recommendation,
            True,
        )

        main()

        # get_recommendations가 호출되었는지 확인
        mock_get_recommendations.assert_called_once_with(user_id=1, limit=20)

        # JobRecommendation이 저장되었는지 확인
        self.assertEqual(mock_job_recommendation.objects.update_or_create.call_count, 2)

        # Slack 메시지가 전송되었는지 확인
        self.assertTrue(mock_send_slack.called)
        success_call = mock_send_slack.call_args_list[-1][0][0]
        self.assertIn("테스트 회사", success_call)
        self.assertIn("백엔드 개발자", success_call)
        self.assertIn("85점", success_call)

    @patch("run_agent.send_slack_message")
    @patch("run_agent.JobRecommendation")
    @patch("run_agent.get_recommendations")
    @patch("run_agent.Resume")
    @patch("run_agent.settings")
    def test_main_save_failure(
        self,
        mock_settings,
        mock_resume,
        mock_get_recommendations,
        mock_job_recommendation,
        mock_send_slack,
    ):
        """추천 저장 실패 시에도 계속 진행 테스트"""
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

        # Mock Resume
        mock_resume_obj = Mock()
        mock_resume_obj.user_id = 1

        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([mock_resume_obj]))
        mock_resume.objects.all.return_value = mock_queryset

        # Mock get_recommendations
        mock_get_recommendations.return_value = [
            {
                "posting_id": 1001,
                "company_name": "테스트 회사",
                "position": "백엔드 개발자",
                "url": "https://example.com/job/1",
                "match_score": 85,
                "match_reason": "필수 스킬 5/6개 보유",
            },
        ]

        # Mock JobRecommendation.objects.update_or_create - 예외 발생
        mock_job_recommendation.objects.update_or_create.side_effect = Exception(
            "Database error"
        )

        main()

        # 에러가 발생해도 Slack 메시지는 전송되어야 함 (빈 추천으로)
        self.assertTrue(mock_send_slack.called)

    @patch("run_agent.send_slack_message")
    @patch("run_agent.get_recommendations")
    @patch("run_agent.Resume")
    @patch("run_agent.settings")
    def test_main_recommendation_exception(
        self, mock_settings, mock_resume, mock_get_recommendations, mock_send_slack
    ):
        """추천 엔진 예외 발생 테스트"""
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

        # Mock Resume
        mock_resume_obj = Mock()
        mock_resume_obj.user_id = 1

        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([mock_resume_obj]))
        mock_resume.objects.all.return_value = mock_queryset

        # Mock get_recommendations - 예외 발생
        mock_get_recommendations.side_effect = Exception("ChromaDB connection error")

        main()

        # 에러 메시지가 전송되었는지 확인
        self.assertTrue(mock_send_slack.called)
        error_calls = [
            call for call in mock_send_slack.call_args_list if "오류" in str(call)
        ]
        self.assertTrue(len(error_calls) > 0)

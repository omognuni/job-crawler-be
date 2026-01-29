from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from user.adapters.google_oauth_http_client import GoogleOAuthHttpClient
from user.domain.google_oauth import GoogleTokenResponse, GoogleUserInfo
from user.models import OAuthAuthorizationRequest


@pytest.mark.django_db
class TestGoogleOAuthCallback:
    def setup_method(self):
        self.client = APIClient()

    def test_callback_returns_404_when_feature_disabled(self, settings):
        settings.GOOGLE_OAUTH_ENABLED = False
        settings.GOOGLE_OAUTH_CLIENT_ID = "dummy-client-id"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "dummy-client-secret"

        resp = self.client.post(
            "/api/v1/users/oauth/google/callback/",
            data={"code": "dummy", "state": "whatever"},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_callback_state_not_found(self, settings):
        settings.GOOGLE_OAUTH_ENABLED = True
        settings.GOOGLE_OAUTH_CLIENT_ID = "dummy-client-id"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "dummy-client-secret"

        resp = self.client.post(
            "/api/v1/users/oauth/google/callback/",
            data={"code": "dummy", "state": "missing"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["error_code"] == "STATE_NOT_FOUND"

    def test_callback_state_expired(self, settings):
        settings.GOOGLE_OAUTH_ENABLED = True
        settings.GOOGLE_OAUTH_CLIENT_ID = "dummy-client-id"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "dummy-client-secret"

        OAuthAuthorizationRequest.objects.create(
            provider="google",
            state="expired",
            redirect_uri="http://localhost:3000/auth/google/callback",
            code_verifier="v",
            code_challenge="c",
            code_challenge_method="S256",
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        resp = self.client.post(
            "/api/v1/users/oauth/google/callback/",
            data={"code": "dummy", "state": "expired"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["error_code"] == "STATE_EXPIRED"

        obj = OAuthAuthorizationRequest.objects.get(state="expired")
        assert obj.used_at is None

    def test_callback_state_already_used(self, settings):
        settings.GOOGLE_OAUTH_ENABLED = True
        settings.GOOGLE_OAUTH_CLIENT_ID = "dummy-client-id"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "dummy-client-secret"

        OAuthAuthorizationRequest.objects.create(
            provider="google",
            state="used",
            redirect_uri="http://localhost:3000/auth/google/callback",
            code_verifier="v",
            code_challenge="c",
            code_challenge_method="S256",
            expires_at=timezone.now() + timedelta(minutes=10),
            used_at=timezone.now(),
        )

        resp = self.client.post(
            "/api/v1/users/oauth/google/callback/",
            data={"code": "dummy", "state": "used"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["error_code"] == "STATE_ALREADY_USED"

    def test_callback_success_sets_jwt_cookies_and_marks_state_used(
        self, settings, monkeypatch
    ):
        settings.GOOGLE_OAUTH_ENABLED = True
        settings.GOOGLE_OAUTH_CLIENT_ID = "dummy-client-id"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "dummy-client-secret"

        OAuthAuthorizationRequest.objects.create(
            provider="google",
            state="ok",
            redirect_uri="http://localhost:3000/auth/google/callback",
            code_verifier="verifier",
            code_challenge="challenge",
            code_challenge_method="S256",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        def fake_exchange(
            self, *, code, client_id, client_secret, redirect_uri, code_verifier
        ):
            assert code == "auth-code"
            assert client_id == "dummy-client-id"
            assert client_secret == "dummy-client-secret"
            assert redirect_uri == "http://localhost:3000/auth/google/callback"
            assert code_verifier == "verifier"
            return GoogleTokenResponse(access_token="access-token")

        def fake_userinfo(self, *, access_token):
            assert access_token == "access-token"
            return GoogleUserInfo(
                sub="sub123",
                email="u@example.com",
                email_verified=True,
                name="User Display",
            )

        monkeypatch.setattr(
            GoogleOAuthHttpClient, "exchange_code_for_token", fake_exchange
        )
        monkeypatch.setattr(GoogleOAuthHttpClient, "fetch_userinfo", fake_userinfo)

        resp = self.client.post(
            "/api/v1/users/oauth/google/callback/",
            data={"code": "auth-code", "state": "ok"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        # 응답 body에는 토큰 대신 사용자 정보만 포함되고,
        # JWT 토큰은 HttpOnly Cookie로 설정된다.
        assert "user" in resp.data
        assert resp.data["user"]["username"] == "google_sub123"
        assert resp.data["user"]["display_name"] == "User Display"

        # JWT 쿠키가 설정되었는지 확인
        access_cookie = resp.cookies.get("access_token")
        refresh_cookie = resp.cookies.get("refresh_token")
        assert access_cookie is not None
        assert refresh_cookie is not None
        assert access_cookie.value
        assert refresh_cookie.value

        obj = OAuthAuthorizationRequest.objects.get(state="ok")
        assert obj.used_at is not None

    def test_callback_does_not_leak_token_like_details_on_exchange_failure(
        self, settings, monkeypatch
    ):
        settings.GOOGLE_OAUTH_ENABLED = True
        settings.GOOGLE_OAUTH_CLIENT_ID = "dummy-client-id"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "dummy-client-secret"

        OAuthAuthorizationRequest.objects.create(
            provider="google",
            state="fail",
            redirect_uri="http://localhost:3000/auth/google/callback",
            code_verifier="verifier",
            code_challenge="challenge",
            code_challenge_method="S256",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        def boom(self, **kwargs):
            raise RuntimeError("access_token=SECRET_ACCESS_TOKEN client_secret=SECRET")

        monkeypatch.setattr(GoogleOAuthHttpClient, "exchange_code_for_token", boom)

        resp = self.client.post(
            "/api/v1/users/oauth/google/callback/",
            data={"code": "auth-code", "state": "fail"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["error_code"] == "TOKEN_EXCHANGE_FAILED"
        dumped = str(resp.data)
        assert "SECRET_ACCESS_TOKEN" not in dumped
        assert "client_secret" not in dumped.lower()

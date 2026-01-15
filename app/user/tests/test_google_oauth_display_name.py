from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from user.adapters.google_oauth_http_client import GoogleOAuthHttpClient
from user.domain.google_oauth import GoogleTokenResponse, GoogleUserInfo
from user.models import OAuthAuthorizationRequest, User


@pytest.mark.django_db
class TestGoogleOAuthDisplayName:
    def setup_method(self):
        self.client = APIClient()

    def test_callback_links_existing_email_user_and_sets_display_name_if_missing(
        self, settings, monkeypatch
    ):
        settings.GOOGLE_OAUTH_ENABLED = True
        settings.GOOGLE_OAUTH_CLIENT_ID = "dummy-client-id"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "dummy-client-secret"

        existing = User.objects.create(username="local_user", email="u@example.com")
        assert not existing.display_name

        OAuthAuthorizationRequest.objects.create(
            provider="google",
            state="ok-link",
            redirect_uri="http://localhost:3000/auth/google/callback",
            code_verifier="verifier",
            code_challenge="challenge",
            code_challenge_method="S256",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        monkeypatch.setattr(
            GoogleOAuthHttpClient,
            "exchange_code_for_token",
            lambda self, **kwargs: GoogleTokenResponse(access_token="access-token"),
        )
        monkeypatch.setattr(
            GoogleOAuthHttpClient,
            "fetch_userinfo",
            lambda self, **kwargs: GoogleUserInfo(
                sub="sub999",
                email="u@example.com",
                email_verified=True,
                name="Linked Name",
            ),
        )

        resp = self.client.post(
            "/api/v1/users/oauth/google/callback/",
            data={"code": "auth-code", "state": "ok-link"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK

        existing.refresh_from_db()
        assert existing.display_name == "Linked Name"
        assert resp.data["user"]["display_name"] == "Linked Name"
        assert resp.data["user"]["id"] == existing.id

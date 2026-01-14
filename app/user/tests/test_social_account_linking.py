from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from user.adapters.google_oauth_http_client import GoogleOAuthHttpClient
from user.domain.google_oauth import GoogleTokenResponse, GoogleUserInfo
from user.models import OAuthAuthorizationRequest, User, UserSocialAccount


@pytest.mark.django_db
class TestGoogleSocialAccountLinking:
    def setup_method(self):
        self.client = APIClient()

    def _seed_oauth_state(self, *, state: str, code_verifier: str = "verifier"):
        OAuthAuthorizationRequest.objects.create(
            provider="google",
            state=state,
            redirect_uri="http://localhost:3000/auth/google/callback",
            code_verifier=code_verifier,
            code_challenge="challenge",
            code_challenge_method="S256",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

    def test_existing_social_by_sub_returns_same_user(self, settings, monkeypatch):
        settings.GOOGLE_OAUTH_ENABLED = True
        settings.GOOGLE_OAUTH_CLIENT_ID = "dummy-client-id"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "dummy-client-secret"

        u = User.objects.create(username="u1", email="u1@example.com")
        u.set_unusable_password()
        u.save(update_fields=["password"])
        UserSocialAccount.objects.create(
            user=u,
            provider="google",
            subject="sub123",
            email="u1@example.com",
            email_verified=True,
        )

        self._seed_oauth_state(state="ok")

        monkeypatch.setattr(
            GoogleOAuthHttpClient,
            "exchange_code_for_token",
            lambda self, **kwargs: GoogleTokenResponse(access_token="access-token"),
        )
        monkeypatch.setattr(
            GoogleOAuthHttpClient,
            "fetch_userinfo",
            lambda self, **kwargs: GoogleUserInfo(
                sub="sub123", email="u1@example.com", email_verified=True
            ),
        )

        resp = self.client.post(
            "/api/v1/users/oauth/google/callback/",
            data={"code": "auth-code", "state": "ok"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert (
            UserSocialAccount.objects.filter(
                provider="google", subject="sub123"
            ).count()
            == 1
        )

    def test_email_verified_existing_user_links_social_account(
        self, settings, monkeypatch
    ):
        settings.GOOGLE_OAUTH_ENABLED = True
        settings.GOOGLE_OAUTH_CLIENT_ID = "dummy-client-id"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "dummy-client-secret"

        existing = User.objects.create(username="existing", email="same@example.com")
        existing.set_unusable_password()
        existing.save(update_fields=["password"])

        self._seed_oauth_state(state="ok2")

        monkeypatch.setattr(
            GoogleOAuthHttpClient,
            "exchange_code_for_token",
            lambda self, **kwargs: GoogleTokenResponse(access_token="access-token"),
        )
        monkeypatch.setattr(
            GoogleOAuthHttpClient,
            "fetch_userinfo",
            lambda self, **kwargs: GoogleUserInfo(
                sub="sub_new", email="same@example.com", email_verified=True
            ),
        )

        resp = self.client.post(
            "/api/v1/users/oauth/google/callback/",
            data={"code": "auth-code", "state": "ok2"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        sa = UserSocialAccount.objects.get(provider="google", subject="sub_new")
        assert sa.user_id == existing.id

    def test_email_conflict_when_user_already_linked_to_google(
        self, settings, monkeypatch
    ):
        settings.GOOGLE_OAUTH_ENABLED = True
        settings.GOOGLE_OAUTH_CLIENT_ID = "dummy-client-id"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "dummy-client-secret"

        existing = User.objects.create(username="existing2", email="same2@example.com")
        existing.set_unusable_password()
        existing.save(update_fields=["password"])
        UserSocialAccount.objects.create(
            user=existing,
            provider="google",
            subject="sub_old",
            email="same2@example.com",
            email_verified=True,
        )

        self._seed_oauth_state(state="ok3")

        monkeypatch.setattr(
            GoogleOAuthHttpClient,
            "exchange_code_for_token",
            lambda self, **kwargs: GoogleTokenResponse(access_token="access-token"),
        )
        monkeypatch.setattr(
            GoogleOAuthHttpClient,
            "fetch_userinfo",
            lambda self, **kwargs: GoogleUserInfo(
                sub="sub_new2", email="same2@example.com", email_verified=True
            ),
        )

        resp = self.client.post(
            "/api/v1/users/oauth/google/callback/",
            data={"code": "auth-code", "state": "ok3"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["error_code"] == "ACCOUNT_CONFLICT"

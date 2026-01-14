import urllib.parse

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient
from user.models import OAuthAuthorizationRequest


@pytest.mark.django_db
class TestGoogleOAuthStart:
    def setup_method(self):
        self.client = APIClient()

    def test_start_rejects_not_allowed_redirect_uri(self):
        with override_settings(
            GOOGLE_OAUTH_ENABLED=True,
            GOOGLE_OAUTH_CLIENT_ID="dummy-client-id",
            GOOGLE_OAUTH_ALLOWED_REDIRECT_URIS=[
                "http://localhost:3000/auth/google/callback"
            ],
            GOOGLE_OAUTH_STATE_TTL_SECONDS=600,
        ):
            resp = self.client.post(
                "/api/v1/users/oauth/google/start/",
                data={"redirect_uri": "http://evil.com/callback"},
                format="json",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["error_code"] == "INVALID_REDIRECT_URI"

    def test_start_creates_state_and_returns_authorization_url(self):
        allowed = "http://localhost:3000/auth/google/callback"
        with override_settings(
            GOOGLE_OAUTH_ENABLED=True,
            GOOGLE_OAUTH_CLIENT_ID="dummy-client-id",
            GOOGLE_OAUTH_ALLOWED_REDIRECT_URIS=[allowed],
            GOOGLE_OAUTH_STATE_TTL_SECONDS=600,
        ):
            resp = self.client.post(
                "/api/v1/users/oauth/google/start/",
                data={"redirect_uri": allowed},
                format="json",
            )

        assert resp.status_code == status.HTTP_200_OK
        assert "authorization_url" in resp.data
        assert "state" in resp.data

        state = resp.data["state"]
        req = OAuthAuthorizationRequest.objects.get(state=state)
        assert req.provider == "google"
        assert req.redirect_uri == allowed
        assert req.code_verifier
        assert req.code_challenge
        assert req.code_challenge_method == "S256"

        parsed = urllib.parse.urlparse(resp.data["authorization_url"])
        assert parsed.netloc == "accounts.google.com"
        qs = urllib.parse.parse_qs(parsed.query)
        assert qs["client_id"] == ["dummy-client-id"]
        assert qs["redirect_uri"] == [allowed]
        assert qs["response_type"] == ["code"]
        assert qs["state"] == [state]
        assert qs["code_challenge_method"] == ["S256"]
        assert qs["code_challenge"] == [req.code_challenge]

    def test_start_returns_404_when_feature_disabled(self):
        allowed = "http://localhost:3000/auth/google/callback"
        with override_settings(
            GOOGLE_OAUTH_ENABLED=False,
            GOOGLE_OAUTH_CLIENT_ID="dummy-client-id",
            GOOGLE_OAUTH_ALLOWED_REDIRECT_URIS=[allowed],
            GOOGLE_OAUTH_STATE_TTL_SECONDS=600,
        ):
            resp = self.client.post(
                "/api/v1/users/oauth/google/start/",
                data={"redirect_uri": allowed},
                format="json",
            )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

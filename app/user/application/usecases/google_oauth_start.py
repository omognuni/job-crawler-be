from __future__ import annotations

import hashlib
import secrets
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from common.application.result import Err, Ok, Result
from user.ports.oauth_request_repo import OAuthAuthorizationRequestRepositoryPort


@dataclass(frozen=True, slots=True)
class GoogleOAuthStartResult:
    authorization_url: str
    state: str


class GoogleOAuthStartUseCase:
    """
    Google OAuth 시작 유스케이스 (SCRUM-21).

    - state/PKCE 생성 및 저장
    - 허용된 redirect_uri만 사용
    - Google authorization URL 생성
    """

    def __init__(
        self,
        *,
        oauth_request_repo: OAuthAuthorizationRequestRepositoryPort,
        enabled: bool,
        google_client_id: str | None,
        allowed_redirect_uris: list[str],
        state_ttl_seconds: int,
    ):
        self._repo = oauth_request_repo
        self._enabled = enabled
        self._google_client_id = google_client_id
        self._allowed_redirect_uris = allowed_redirect_uris
        self._state_ttl_seconds = state_ttl_seconds

    def execute(self, *, redirect_uri: str) -> Result[GoogleOAuthStartResult]:
        if not self._enabled:
            return Err(code="FEATURE_DISABLED", message="Google OAuth is disabled")
        if not self._google_client_id:
            return Err(
                code="CONFIG_MISSING",
                message="Google OAuth client_id is not configured",
            )

        if redirect_uri not in self._allowed_redirect_uris:
            return Err(
                code="INVALID_REDIRECT_URI",
                message="redirect_uri is not allowed",
                details={"redirect_uri": redirect_uri},
            )

        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = _build_code_challenge(code_verifier)

        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=max(1, int(self._state_ttl_seconds))
        )
        self._repo.create(
            provider="google",
            state=state,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            code_challenge=code_challenge,
            code_challenge_method="S256",
            expires_at=expires_at,
        )

        authorization_url = _build_google_authorization_url(
            client_id=self._google_client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=code_challenge,
        )
        return Ok(
            GoogleOAuthStartResult(authorization_url=authorization_url, state=state)
        )


def _base64url(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _build_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return _base64url(digest)


def _build_google_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    base = "https://accounts.google.com/o/oauth2/v2/auth"
    query = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{base}?{urllib.parse.urlencode(query)}"

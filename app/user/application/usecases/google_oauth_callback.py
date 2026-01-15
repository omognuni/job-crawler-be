from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from common.application.result import Err, Ok, Result
from common.masking import mask_secrets
from user.ports.google_oauth_client import GoogleOAuthClientPort
from user.ports.oauth_request_repo import OAuthAuthorizationRequestRepositoryPort
from user.ports.user_repo import UserRepositoryPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GoogleOAuthCallbackResult:
    user_id: int
    display_name: str | None = None


class GoogleOAuthCallbackUseCase:
    """
    Google OAuth 콜백 처리 유스케이스 (SCRUM-23).

    - state 검증/만료/재사용 방지(consume)
    - code -> token 교환 (PKCE verifier 포함)
    - userinfo 조회 및 최소 검증(email_verified)
    - 서비스 유저 식별/생성(임시: google_{sub})
    """

    def __init__(
        self,
        *,
        oauth_request_repo: OAuthAuthorizationRequestRepositoryPort,
        google_oauth_client: GoogleOAuthClientPort,
        user_repo: UserRepositoryPort,
        enabled: bool,
        google_client_id: str | None,
        google_client_secret: str | None,
    ):
        self._oauth_request_repo = oauth_request_repo
        self._google_oauth_client = google_oauth_client
        self._user_repo = user_repo
        self._enabled = enabled
        self._google_client_id = google_client_id
        self._google_client_secret = google_client_secret

    def execute(self, *, code: str, state: str) -> Result[GoogleOAuthCallbackResult]:
        if not self._enabled:
            return Err(code="FEATURE_DISABLED", message="Google OAuth is disabled")
        if not self._google_client_id or not self._google_client_secret:
            return Err(
                code="CONFIG_MISSING",
                message="Google OAuth client_id/client_secret is not configured",
            )

        now = datetime.now(timezone.utc)
        consumed = self._oauth_request_repo.consume_by_state(
            provider="google", state=state, now=now
        )
        if isinstance(consumed, Err):
            return consumed

        assert isinstance(consumed, Ok)
        req = consumed.value

        try:
            token = self._google_oauth_client.exchange_code_for_token(
                code=code,
                client_id=self._google_client_id,
                client_secret=self._google_client_secret,
                redirect_uri=req.redirect_uri,
                code_verifier=req.code_verifier,
            )
        except Exception as e:
            logger.warning(
                "google_oauth_token_exchange_failed provider=google state_hash=%s reason=%s",
                _state_hash(state),
                mask_secrets(str(e)),
            )
            return Err(
                code="TOKEN_EXCHANGE_FAILED",
                message="Failed to exchange code for token",
            )

        try:
            userinfo = self._google_oauth_client.fetch_userinfo(
                access_token=token.access_token
            )
        except Exception as e:
            logger.warning(
                "google_oauth_userinfo_failed provider=google state_hash=%s reason=%s",
                _state_hash(state),
                mask_secrets(str(e)),
            )
            return Err(
                code="USERINFO_FAILED",
                message="Failed to fetch user info",
            )

        if not userinfo.email_verified:
            return Err(code="EMAIL_NOT_VERIFIED", message="Email is not verified")

        user_id_result = self._user_repo.get_or_create_google_user(
            subject=userinfo.sub,
            email=userinfo.email,
            email_verified=bool(userinfo.email_verified),
        )
        if isinstance(user_id_result, Err):
            return user_id_result
        assert isinstance(user_id_result, Ok)
        return Ok(
            GoogleOAuthCallbackResult(
                user_id=int(user_id_result.value),
                display_name=userinfo.name,
            )
        )


def _state_hash(state: str) -> str:
    import hashlib

    return hashlib.sha256(state.encode("utf-8")).hexdigest()[:8]

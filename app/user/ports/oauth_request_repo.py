from __future__ import annotations

from datetime import datetime
from typing import Protocol

from common.application.result import Result
from user.domain.oauth_request import OAuthAuthorizationRequestDomain


class OAuthAuthorizationRequestRepositoryPort(Protocol):
    def create(
        self,
        *,
        provider: str,
        state: str,
        redirect_uri: str,
        code_verifier: str,
        code_challenge: str,
        code_challenge_method: str,
        expires_at: datetime,
    ) -> OAuthAuthorizationRequestDomain: ...

    def consume_by_state(
        self,
        *,
        provider: str,
        state: str,
        now: datetime,
    ) -> Result[OAuthAuthorizationRequestDomain]: ...

from __future__ import annotations

from typing import Protocol

from user.domain.google_oauth import GoogleTokenResponse, GoogleUserInfo


class GoogleOAuthClientPort(Protocol):
    def exchange_code_for_token(
        self,
        *,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> GoogleTokenResponse: ...

    def fetch_userinfo(self, *, access_token: str) -> GoogleUserInfo: ...

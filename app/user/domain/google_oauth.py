from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoogleTokenResponse:
    access_token: str
    id_token: str | None = None
    expires_in: int | None = None
    token_type: str | None = None


@dataclass(frozen=True, slots=True)
class GoogleUserInfo:
    sub: str
    email: str | None
    email_verified: bool
    name: str | None = None

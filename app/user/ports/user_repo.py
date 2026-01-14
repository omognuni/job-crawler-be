from __future__ import annotations

from typing import Protocol

from common.application.result import Result


class UserRepositoryPort(Protocol):
    def get_or_create_google_user(
        self,
        *,
        subject: str,
        email: str | None,
        email_verified: bool,
    ) -> Result[int]: ...

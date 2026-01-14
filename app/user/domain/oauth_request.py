from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class OAuthAuthorizationRequestDomain:
    provider: str
    state: str
    redirect_uri: str
    code_verifier: str
    code_challenge: str
    code_challenge_method: str
    expires_at: datetime

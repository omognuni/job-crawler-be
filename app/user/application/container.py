from __future__ import annotations

from django.conf import settings
from user.adapters.django_oauth_request_repo import (
    DjangoOAuthAuthorizationRequestRepository,
)
from user.adapters.django_user_repo import DjangoUserRepository
from user.adapters.google_oauth_http_client import GoogleOAuthHttpClient
from user.application.usecases.google_oauth_callback import GoogleOAuthCallbackUseCase
from user.application.usecases.google_oauth_start import GoogleOAuthStartUseCase


def build_google_oauth_start_usecase() -> GoogleOAuthStartUseCase:
    return GoogleOAuthStartUseCase(
        oauth_request_repo=DjangoOAuthAuthorizationRequestRepository(),
        enabled=bool(getattr(settings, "GOOGLE_OAUTH_ENABLED", False)),
        google_client_id=getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None),
        allowed_redirect_uris=getattr(
            settings, "GOOGLE_OAUTH_ALLOWED_REDIRECT_URIS", []
        ),
        state_ttl_seconds=getattr(settings, "GOOGLE_OAUTH_STATE_TTL_SECONDS", 600),
    )


def build_google_oauth_callback_usecase() -> GoogleOAuthCallbackUseCase:
    return GoogleOAuthCallbackUseCase(
        oauth_request_repo=DjangoOAuthAuthorizationRequestRepository(),
        google_oauth_client=GoogleOAuthHttpClient(),
        user_repo=DjangoUserRepository(),
        enabled=bool(getattr(settings, "GOOGLE_OAUTH_ENABLED", False)),
        google_client_id=getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None),
        google_client_secret=getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", None),
    )

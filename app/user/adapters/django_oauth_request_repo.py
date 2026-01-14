from __future__ import annotations

from datetime import datetime

from common.application.result import Err, Ok, Result
from django.db import transaction
from django.utils import timezone
from user.domain.oauth_request import OAuthAuthorizationRequestDomain
from user.models import OAuthAuthorizationRequest
from user.ports.oauth_request_repo import OAuthAuthorizationRequestRepositoryPort


class DjangoOAuthAuthorizationRequestRepository(
    OAuthAuthorizationRequestRepositoryPort
):
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
    ) -> OAuthAuthorizationRequestDomain:
        # DB에는 timezone-aware datetime을 저장하는 것이 안전합니다.
        if timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at)

        obj = OAuthAuthorizationRequest.objects.create(
            provider=provider,
            state=state,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=expires_at,
        )
        return OAuthAuthorizationRequestDomain(
            provider=obj.provider,
            state=obj.state,
            redirect_uri=obj.redirect_uri,
            code_verifier=obj.code_verifier,
            code_challenge=obj.code_challenge,
            code_challenge_method=obj.code_challenge_method,
            expires_at=obj.expires_at,
        )

    def consume_by_state(
        self,
        *,
        provider: str,
        state: str,
        now: datetime,
    ) -> Result[OAuthAuthorizationRequestDomain]:
        """
        state를 원자적으로 소비(재사용 방지)합니다.

        - Not found / expired / already used 를 구분해 Err로 반환
        """
        if timezone.is_naive(now):
            now = timezone.make_aware(now)

        with transaction.atomic():
            obj = (
                OAuthAuthorizationRequest.objects.select_for_update()
                .filter(provider=provider, state=state)
                .first()
            )
            if obj is None:
                return Err(code="STATE_NOT_FOUND", message="state not found")

            if obj.used_at is not None:
                return Err(code="STATE_ALREADY_USED", message="state already used")

            if obj.expires_at <= now:
                return Err(code="STATE_EXPIRED", message="state expired")

            obj.used_at = now
            obj.save(update_fields=["used_at"])

            return Ok(
                OAuthAuthorizationRequestDomain(
                    provider=obj.provider,
                    state=obj.state,
                    redirect_uri=obj.redirect_uri,
                    code_verifier=obj.code_verifier,
                    code_challenge=obj.code_challenge,
                    code_challenge_method=obj.code_challenge_method,
                    expires_at=obj.expires_at,
                )
            )

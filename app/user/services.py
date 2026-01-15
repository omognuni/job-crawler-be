from __future__ import annotations

from common.application.result import Err, Ok, Result
from rest_framework_simplejwt.tokens import RefreshToken
from user.application.container import (
    build_google_oauth_callback_usecase,
    build_google_oauth_start_usecase,
)
from user.application.usecases.google_oauth_start import GoogleOAuthStartResult
from user.models import User


class UserOAuthService:
    @staticmethod
    def start_google_oauth(*, redirect_uri: str) -> Result[GoogleOAuthStartResult]:
        usecase = build_google_oauth_start_usecase()
        return usecase.execute(redirect_uri=redirect_uri)

    @staticmethod
    def complete_google_oauth(*, code: str, state: str) -> Result[dict]:
        """
        Google OAuth 콜백 처리(SCRUM-23).

        - 유스케이스에서 user_id까지 확보
        - 여기서 JWT를 발급해 응답 형태로 반환
        """
        usecase = build_google_oauth_callback_usecase()
        result = usecase.execute(code=code, state=state)
        if isinstance(result, Err):
            return result

        assert isinstance(result, Ok)
        user = User.objects.get(pk=result.value.user_id)
        # display_name은 "비어있는 경우"에만 Google name으로 채운다(기존 유저가 직접 설정한 값은 덮어쓰지 않음)
        if result.value.display_name and not user.display_name:
            user.display_name = result.value.display_name
            user.save(update_fields=["display_name"])
        refresh = RefreshToken.for_user(user)
        return Ok(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": {
                    "id": int(user.id),
                    "username": user.username,
                    "display_name": user.display_name,
                },
            }
        )

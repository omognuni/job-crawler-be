"""
JWT Cookie Authentication (SCRUM-34)

HttpOnly Cookie 또는 Authorization 헤더에서 JWT를 읽어 인증하는 래퍼.
"""

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTCookieAuthentication(JWTAuthentication):
    """
    1) Authorization 헤더 (기존 방식)
    2) Cookie (access_token)
    순으로 토큰을 찾아 인증.
    """

    def authenticate(self, request):
        header = super().authenticate(request)
        if header is not None:
            return header

        cookie_name = getattr(settings, "JWT_AUTH_COOKIE", "access_token")
        raw = request.COOKIES.get(cookie_name)
        if raw is None:
            return None

        validated = self.get_validated_token(raw)
        return self.get_user(validated), validated

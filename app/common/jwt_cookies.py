"""
JWT Cookie Utilities (SCRUM-34)

HttpOnly Cookie로 JWT 토큰을 설정/삭제하는 래퍼.
XSS 방어: JavaScript에서 토큰 접근 불가.
"""

from django.conf import settings
from rest_framework.response import Response


def set_jwt_cookies(
    response: Response, access_token: str, refresh_token: str
) -> Response:
    """응답에 JWT를 HttpOnly Cookie로 설정."""
    access_name = getattr(settings, "JWT_AUTH_COOKIE", "access_token")
    refresh_name = getattr(settings, "JWT_AUTH_REFRESH_COOKIE", "refresh_token")
    httponly = getattr(settings, "JWT_AUTH_COOKIE_HTTP_ONLY", True)
    secure = getattr(settings, "JWT_AUTH_COOKIE_SECURE", not settings.DEBUG)
    samesite = getattr(settings, "JWT_AUTH_COOKIE_SAMESITE", "Lax")
    path = getattr(settings, "JWT_AUTH_COOKIE_PATH", "/")
    domain = getattr(settings, "JWT_AUTH_COOKIE_DOMAIN", None)

    response.set_cookie(
        key=access_name,
        value=access_token,
        httponly=httponly,
        secure=secure,
        samesite=samesite,
        path=path,
        domain=domain,
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
    )
    response.set_cookie(
        key=refresh_name,
        value=refresh_token,
        httponly=httponly,
        secure=secure,
        samesite=samesite,
        path=path,
        domain=domain,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
    )
    return response


def delete_jwt_cookies(response: Response) -> Response:
    """JWT Cookie 삭제 (로그아웃용)."""
    access_name = getattr(settings, "JWT_AUTH_COOKIE", "access_token")
    refresh_name = getattr(settings, "JWT_AUTH_REFRESH_COOKIE", "refresh_token")
    path = getattr(settings, "JWT_AUTH_COOKIE_PATH", "/")
    domain = getattr(settings, "JWT_AUTH_COOKIE_DOMAIN", None)
    samesite = getattr(settings, "JWT_AUTH_COOKIE_SAMESITE", "Lax")

    response.delete_cookie(key=access_name, path=path, domain=domain, samesite=samesite)
    response.delete_cookie(
        key=refresh_name, path=path, domain=domain, samesite=samesite
    )
    return response

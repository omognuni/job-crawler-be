from django.conf import settings
from rest_framework.permissions import BasePermission


class HasSimpleSecretKey(BasePermission):
    """
    'X-API-KEY' 헤더에 유효한 API 키가 있는지 확인합니다.

    보안을 위해 Django SECRET_KEY와 별도의 API_SECRET_KEY를 사용합니다.
    """

    def has_permission(self, request, view):
        expected_key = settings.API_SECRET_KEY
        provided_key = request.headers.get("X-API-KEY")

        return provided_key == expected_key

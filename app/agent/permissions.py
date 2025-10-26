from django.conf import settings
from rest_framework.permissions import BasePermission


class HasSimpleSecretKey(BasePermission):
    """
    'X-API-KEY' 헤더에 유효한 비밀 키가 있는지 확인합니다.
    """

    def has_permission(self, request, view):
        expected_key = settings.SECRET_KEY
        provided_key = request.headers.get("X-API-KEY")

        return provided_key == expected_key

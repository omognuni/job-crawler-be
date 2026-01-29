from common.application.result import Err, Ok
from common.jwt_cookies import delete_jwt_cookies, set_jwt_cookies
from django.conf import settings
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from user.serializers import (
    GoogleOAuthCallbackSerializer,
    GoogleOAuthStartSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
)
from user.services import UserOAuthService


class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = []


class UserLoginView(APIView):
    permission_classes = []

    @extend_schema(
        request=UserLoginSerializer,
        responses={200: OpenApiTypes.OBJECT},
        summary="User Login",
        description="Login with email and password. JWT is set as HttpOnly cookies.",
    )
    def post(self, request):
        serializer = UserLoginSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "display_name": getattr(user, "display_name", None),
                },
            },
            status=status.HTTP_200_OK,
        )
        return set_jwt_cookies(
            response,
            access_token=str(refresh.access_token),
            refresh_token=str(refresh),
        )


class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OpenApiTypes.OBJECT},
        summary="User Logout",
        description="Clear JWT cookies.",
    )
    def post(self, request):
        response = Response(
            {"message": "Logout successful"},
            status=status.HTTP_200_OK,
        )
        return delete_jwt_cookies(response)


class TokenRefreshCookieView(APIView):
    """Refresh access token from HttpOnly refresh_token cookie."""

    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: OpenApiTypes.OBJECT},
        summary="Refresh Token",
        description="Refresh access token using refresh_token cookie.",
    )
    def post(self, request):
        refresh_name = getattr(settings, "JWT_AUTH_REFRESH_COOKIE", "refresh_token")
        raw = request.COOKIES.get(refresh_name)
        if not raw:
            return Response(
                {"error": "Refresh token not found in cookies"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            refresh = RefreshToken(raw)
            access = str(refresh.access_token)
            response = Response(
                {"message": "Token refreshed"},
                status=status.HTTP_200_OK,
            )
            response.set_cookie(
                key=getattr(settings, "JWT_AUTH_COOKIE", "access_token"),
                value=access,
                httponly=getattr(settings, "JWT_AUTH_COOKIE_HTTP_ONLY", True),
                secure=getattr(settings, "JWT_AUTH_COOKIE_SECURE", not settings.DEBUG),
                samesite=getattr(settings, "JWT_AUTH_COOKIE_SAMESITE", "Lax"),
                path=getattr(settings, "JWT_AUTH_COOKIE_PATH", "/"),
                domain=getattr(settings, "JWT_AUTH_COOKIE_DOMAIN", None),
                max_age=int(
                    settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()
                ),
            )
            return response
        except (InvalidToken, TokenError):
            return Response(
                {"error": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class GoogleOAuthStartView(APIView):
    """
    Google OAuth 시작 엔드포인트 (SCRUM-21)

    POST /api/v1/users/oauth/google/start/
    """

    permission_classes = [AllowAny]

    @extend_schema(
        request=GoogleOAuthStartSerializer,
        responses={200: OpenApiTypes.OBJECT},
        summary="Google OAuth Start",
        description="Create OAuth authorization URL and persist state/PKCE for later callback validation.",
    )
    def post(self, request):
        serializer = GoogleOAuthStartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid request body", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        redirect_uri = serializer.validated_data["redirect_uri"]
        result = UserOAuthService.start_google_oauth(redirect_uri=redirect_uri)
        if isinstance(result, Err):
            if result.code == "FEATURE_DISABLED":
                return Response(status=status.HTTP_404_NOT_FOUND)
            return Response(
                {
                    "error": result.message,
                    "error_code": result.code,
                    "details": result.details or {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        assert isinstance(result, Ok)
        return Response(
            {
                "authorization_url": result.value.authorization_url,
                "state": result.value.state,
            },
            status=status.HTTP_200_OK,
        )


class GoogleOAuthCallbackView(APIView):
    """
    Google OAuth 콜백 처리 엔드포인트 (SCRUM-23)

    POST /api/v1/users/oauth/google/callback/
    """

    permission_classes = [AllowAny]

    @extend_schema(
        request=GoogleOAuthCallbackSerializer,
        responses={200: OpenApiTypes.OBJECT},
        summary="Google OAuth Callback",
        description="Validate state, exchange code for token, fetch userinfo, and issue JWT as HttpOnly cookies.",
    )
    def post(self, request):
        serializer = GoogleOAuthCallbackSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid request body", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = serializer.validated_data["code"]
        state = serializer.validated_data["state"]
        result = UserOAuthService.complete_google_oauth(code=code, state=state)
        if isinstance(result, Err):
            if result.code == "FEATURE_DISABLED":
                return Response(status=status.HTTP_404_NOT_FOUND)
            return Response(
                {
                    "error": result.message,
                    "error_code": result.code,
                    "details": result.details or {},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        assert isinstance(result, Ok)
        data = result.value
        response = Response(
            {"message": "OAuth login successful", "user": data.get("user")},
            status=status.HTTP_200_OK,
        )
        return set_jwt_cookies(
            response,
            access_token=data["access"],
            refresh_token=data["refresh"],
        )

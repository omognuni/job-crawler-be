from common.application.result import Err, Ok
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
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
    permission_classes = []  # No permission required for registration


class UserLoginView(APIView):
    permission_classes = []  # No permission required for login

    @extend_schema(
        request=UserLoginSerializer,
        responses={
            200: OpenApiTypes.OBJECT,  # Or define a serializer for the response if needed
        },
        summary="User Login",
        description="Login with email and password to get JWT tokens.",
    )
    def post(self, request):
        serializer = UserLoginSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_200_OK,
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
        description="Validate state, exchange code for token, fetch userinfo, and issue JWT tokens.",
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
        return Response(result.value, status=status.HTTP_200_OK)

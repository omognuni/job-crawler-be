from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from user.serializers import UserLoginSerializer, UserRegistrationSerializer


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

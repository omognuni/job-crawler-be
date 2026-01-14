from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from user.views import (
    GoogleOAuthCallbackView,
    GoogleOAuthStartView,
    UserLoginView,
    UserRegistrationView,
)

urlpatterns = [
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("login/", UserLoginView.as_view(), name="login"),
    path(
        "oauth/google/start/", GoogleOAuthStartView.as_view(), name="google_oauth_start"
    ),
    path(
        "oauth/google/callback/",
        GoogleOAuthCallbackView.as_view(),
        name="google_oauth_callback",
    ),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]

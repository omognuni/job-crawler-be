from django.urls import path
from user.views import (
    GoogleOAuthCallbackView,
    GoogleOAuthStartView,
    TokenRefreshCookieView,
    UserLoginView,
    UserLogoutView,
    UserRegistrationView,
)

urlpatterns = [
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path(
        "oauth/google/start/", GoogleOAuthStartView.as_view(), name="google_oauth_start"
    ),
    path(
        "oauth/google/callback/",
        GoogleOAuthCallbackView.as_view(),
        name="google_oauth_callback",
    ),
    path("token/refresh/", TokenRefreshCookieView.as_view(), name="token_refresh"),
]

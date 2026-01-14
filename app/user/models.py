from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # Add any custom fields here if needed
    pass


class OAuthAuthorizationRequest(models.Model):
    """
    OAuth Authorization Code 플로우 시작 시 생성되는 state/PKCE 저장소.

    - SCRUM-21: OAuth 시작 엔드포인트에서 생성/저장
    - SCRUM-23: 콜백 처리 시 state 검증/재사용 방지에 사용
    """

    PROVIDER_GOOGLE = "google"
    PROVIDER_CHOICES = [(PROVIDER_GOOGLE, "Google")]

    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    state = models.CharField(max_length=128, unique=True)
    redirect_uri = models.URLField(max_length=500)

    # PKCE
    code_verifier = models.CharField(max_length=200)
    code_challenge = models.CharField(max_length=200)
    code_challenge_method = models.CharField(max_length=10, default="S256")

    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["provider", "state"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["used_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return (
            f"OAuthAuthorizationRequest(provider={self.provider}, state={self.state})"
        )


class UserSocialAccount(models.Model):
    """
    소셜 로그인 계정 매핑 테이블 (SCRUM-25).

    - provider + subject(sub) 로 외부 계정을 유일하게 식별
    - email 충돌 시 정책 적용
    """

    PROVIDER_GOOGLE = "google"
    PROVIDER_CHOICES = [(PROVIDER_GOOGLE, "Google")]

    user = models.ForeignKey(
        "user.User", on_delete=models.CASCADE, related_name="social_accounts"
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    subject = models.CharField(max_length=255)

    email = models.EmailField(blank=True, null=True)
    email_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "subject"],
                name="uniq_social_provider_subject",
            ),
            models.UniqueConstraint(
                fields=["user", "provider"],
                name="uniq_social_user_provider",
            ),
        ]
        indexes = [
            models.Index(fields=["provider", "subject"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"UserSocialAccount(provider={self.provider}, subject={self.subject})"

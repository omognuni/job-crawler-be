from __future__ import annotations

from common.application.result import Err, Ok, Result
from django.db import IntegrityError, transaction
from user.models import User, UserSocialAccount
from user.ports.user_repo import UserRepositoryPort


class DjangoUserRepository(UserRepositoryPort):
    def get_or_create_google_user(
        self,
        *,
        subject: str,
        email: str | None,
        email_verified: bool,
    ) -> Result[int]:
        """
        Google 계정으로 유저를 식별/생성/연동합니다. (SCRUM-25)

        정책(안전 우선):
        - 1) provider+subject 로 매핑이 있으면 해당 user 반환
        - 2) 없으면, email_verified=True 이고 email이 존재할 때:
             - 동일 email의 기존 user가 있으면 그 user에 소셜 계정을 "연동"
             - 단, 그 user가 이미 다른 google subject로 연동되어 있으면 충돌(ACCOUNT_CONFLICT)
        - 3) 그 외에는 신규 user 생성 후 소셜 계정 생성
        """
        provider = "google"
        # 1) subject 기준
        existing = (
            UserSocialAccount.objects.select_related("user")
            .filter(provider=provider, subject=subject)
            .first()
        )
        if existing is not None:
            return Ok(int(existing.user_id))

        # 2) 이메일 기반 연동(검증된 이메일만)
        user_to_link: User | None = None
        if email_verified and email:
            user_to_link = User.objects.filter(email=email).first()

        with transaction.atomic():
            if user_to_link is not None:
                # 이미 같은 provider로 연결된 다른 subject가 있으면 충돌
                if UserSocialAccount.objects.filter(
                    user=user_to_link, provider=provider
                ).exists():
                    return Err(
                        code="ACCOUNT_CONFLICT",
                        message="User already linked with a different Google account",
                        details={"email": email},
                    )
                try:
                    UserSocialAccount.objects.create(
                        user=user_to_link,
                        provider=provider,
                        subject=subject,
                        email=email,
                        email_verified=True,
                    )
                except IntegrityError as e:
                    return Err(
                        code="ACCOUNT_CONFLICT",
                        message="Social account conflict",
                        details={"reason": str(e)},
                    )
                return Ok(int(user_to_link.id))

            # 3) 신규 생성
            username = f"google_{subject}"
            user = User.objects.create(username=username, email=email or "")
            user.set_unusable_password()
            user.save(update_fields=["password"])
            UserSocialAccount.objects.create(
                user=user,
                provider=provider,
                subject=subject,
                email=email,
                email_verified=bool(email_verified and email),
            )
            return Ok(int(user.id))

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from user.domain.google_oauth import GoogleTokenResponse, GoogleUserInfo
from user.ports.google_oauth_client import GoogleOAuthClientPort


class GoogleOAuthHttpClient(GoogleOAuthClientPort):
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"

    def exchange_code_for_token(
        self,
        *,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> GoogleTokenResponse:
        data = urllib.parse.urlencode(
            {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # 응답 바디에는 디버그 정보가 포함될 수 있으나, 토큰/PII 누출 위험이 있어
            # 예외 메시지에는 포함하지 않습니다(로그는 상위 레이어에서 마스킹 처리).
            raise RuntimeError(f"token_exchange_failed: http_{e.code}") from e
        except Exception as e:
            raise RuntimeError("token_exchange_failed") from e

        access_token = payload.get("access_token")
        if not access_token:
            raise RuntimeError(f"token_exchange_failed: no access_token ({payload})")

        return GoogleTokenResponse(
            access_token=str(access_token),
            id_token=payload.get("id_token"),
            expires_in=payload.get("expires_in"),
            token_type=payload.get("token_type"),
        )

    def fetch_userinfo(self, *, access_token: str) -> GoogleUserInfo:
        req = urllib.request.Request(
            self.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"userinfo_failed: http_{e.code}") from e
        except Exception as e:
            raise RuntimeError("userinfo_failed") from e

        sub = payload.get("sub")
        if not sub:
            raise RuntimeError(f"userinfo_failed: no sub ({payload})")

        return GoogleUserInfo(
            sub=str(sub),
            email=payload.get("email"),
            email_verified=bool(payload.get("email_verified", False)),
        )

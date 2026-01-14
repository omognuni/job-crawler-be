from __future__ import annotations

import re

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    # naive but useful: don't leak raw bearer tokens / jwt-ish strings
    re.compile(r"Bearer\s+[A-Za-z0-9\-\._~\+/]+=*", re.IGNORECASE),
    re.compile(
        r"\b(access_token|refresh_token|id_token|client_secret)\b\s*[:=]\s*[^\\s,]+",
        re.IGNORECASE,
    ),
]


def mask_secrets(text: str) -> str:
    """
    로그/응답에 민감 정보가 섞이지 않도록 보수적으로 마스킹합니다.
    """
    if not text:
        return text
    masked = text
    for pat in _SECRET_PATTERNS:
        masked = pat.sub("[REDACTED]", masked)
    # 길이가 과도하게 길면 잘라서 로그 폭발을 막음
    if len(masked) > 500:
        masked = masked[:500] + "...[TRUNCATED]"
    return masked

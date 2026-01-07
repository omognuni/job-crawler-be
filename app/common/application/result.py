from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Err:
    """
    유스케이스 실패 결과.

    - code: 프로그램적으로 구분 가능한 에러 코드 (예: "NOT_FOUND", "VALIDATION_ERROR")
    - message: 사용자/로그용 메시지
    - details: 디버깅에 유용한 추가 정보(선택)
    """

    code: str
    message: str
    details: Optional[dict] = None


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    """유스케이스 성공 결과."""

    value: T


Result = Ok[T] | Err

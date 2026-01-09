from __future__ import annotations

from typing import Protocol

from resume.models import Resume


class SearchPlanBuilderPort(Protocol):
    """
    추천 검색전략(쿼리/필터/루브릭)을 생성하는 포트.
    - LLM 기반 구현체를 기본으로 하되, API 키가 없거나 실패하면 fallback을 사용합니다.
    """

    def build_plan(self, *, resume: Resume) -> dict: ...

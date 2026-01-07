from __future__ import annotations

from typing import Protocol


class GraphStorePort(Protocol):
    def upsert_job_posting(
        self,
        *,
        posting_id: int,
        position: str,
        company_name: str,
        skills_required: list[str],
    ) -> None: ...

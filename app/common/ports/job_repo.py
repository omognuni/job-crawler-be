from __future__ import annotations

from typing import Optional, Protocol

from job.models import JobPosting


class JobPostingRepositoryPort(Protocol):
    def get_by_id(self, posting_id: int) -> Optional[JobPosting]: ...

    def save(
        self, job_posting: JobPosting, *, update_fields: Optional[list[str]] = None
    ) -> JobPosting: ...

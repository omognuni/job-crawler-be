from __future__ import annotations

from typing import Optional

from job.models import JobPosting


class DjangoJobPostingRepository:
    def get_by_id(self, posting_id: int) -> Optional[JobPosting]:
        try:
            return JobPosting.objects.get(posting_id=posting_id)
        except JobPosting.DoesNotExist:
            return None

    def save(
        self, job_posting: JobPosting, *, update_fields: Optional[list[str]] = None
    ) -> JobPosting:
        job_posting.save(update_fields=update_fields)
        job_posting.refresh_from_db()
        return job_posting

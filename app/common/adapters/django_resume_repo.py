from __future__ import annotations

from typing import Optional

from resume.models import Resume


class DjangoResumeRepository:
    def get_by_id(self, resume_id: int) -> Optional[Resume]:
        try:
            return Resume.objects.get(id=resume_id)
        except Resume.DoesNotExist:
            return None

    def save(
        self, resume: Resume, *, update_fields: Optional[list[str]] = None
    ) -> Resume:
        resume.save(update_fields=update_fields)
        resume.refresh_from_db()
        return resume

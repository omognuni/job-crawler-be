from __future__ import annotations

from typing import Optional, Protocol

from resume.models import Resume


class ResumeRepositoryPort(Protocol):
    def get_by_id(self, resume_id: int) -> Optional[Resume]: ...

    def save(
        self, resume: Resume, *, update_fields: Optional[list[str]] = None
    ) -> Resume: ...

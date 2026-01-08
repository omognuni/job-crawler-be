from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProcessJobPostingResultDTO(BaseModel):
    success: bool = Field(description="성공 여부")
    posting_id: Optional[int] = Field(default=None, description="채용 공고 ID")
    skills_required: Optional[int] = Field(default=None, description="필수 스킬 개수")
    skills_preferred_text: Optional[str] = Field(
        default=None, description="우대 사항 텍스트(일부)"
    )
    error: Optional[str] = Field(default=None, description="에러 메시지")

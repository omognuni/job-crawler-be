from typing import List, Optional

from pydantic import BaseModel, Field


class ResumeAnalysisResultDTO(BaseModel):
    """
    이력서 분석 결과 DTO
    """

    skills: List[str] = Field(default_factory=list, description="추출된 스킬 목록")
    position: str = Field(default="", description="추천 포지션")
    career_years: int = Field(default=0, ge=0, description="총 경력 연차")
    strengths: str = Field(default="", description="강점 요약")
    experience_summary: str = Field(default="", description="경력 요약 (임베딩용)")


class ProcessResumeResultDTO(BaseModel):
    """
    이력서 처리 결과 DTO
    """

    success: bool = Field(description="성공 여부")
    resume_id: Optional[int] = Field(default=None, description="이력서 ID")
    user_id: Optional[int] = Field(default=None, description="사용자 ID")
    skills_count: Optional[int] = Field(default=None, description="추출된 스킬 개수")
    career_years: Optional[int] = Field(default=None, description="분석된 경력 연차")
    position: Optional[str] = Field(default=None, description="분석된 포지션")
    error: Optional[str] = Field(default=None, description="에러 메시지")

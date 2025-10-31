from pydantic import BaseModel, Field

class JobRecommendation(BaseModel):
    rank: int = Field(..., description="추천 순위 (1-10)")
    url: str = Field(..., description="채용 공고 URL")
    company_name: str = Field(..., description="회사 이름")
    position: str = Field(..., description="채용 포지션")
    match_score: int = Field(..., description="매칭 점수 (0-100)")
    match_reason: str = Field(..., description="구체적인 추천 이유 (한국어 3줄 이내)")

# 2. 'recommend_jobs_task'의 최종 출력 JSON 구조를 정의합니다.
class FinalRecommendationOutput(BaseModel):
    status: str = Field(..., description="작업 상태 (예: 'success')")
    user_id: int = Field(..., description="사용자 ID")
    saved_count: int = Field(..., description="저장된 추천 공고 수")
    recommendations: list[JobRecommendation] = Field(..., description="Top 10 추천 공고 리스트")
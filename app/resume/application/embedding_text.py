from __future__ import annotations

from typing import Optional

from resume.models import Resume


def build_resume_embedding_text(
    resume: Resume,
    *,
    fallback_skills: Optional[list[str]] = None,
    fallback_position: str = "",
    fallback_career_years: int = 0,
) -> tuple[str, dict]:
    """
    이력서 임베딩용 텍스트와 메타데이터를 생성합니다.

    기존 `resume/embeddings.py`의 동작을 유스케이스에서 재사용할 수 있도록 순수 함수화한 버전입니다.
    """
    analysis_result = resume.analysis_result or {}
    skills = (
        analysis_result.get("skills", []) if isinstance(analysis_result, dict) else []
    )
    if not skills and fallback_skills:
        skills = fallback_skills

    position = (
        analysis_result.get("position", "") if isinstance(analysis_result, dict) else ""
    ) or ""
    if not position and fallback_position:
        position = fallback_position

    career_years = (
        analysis_result.get("career_years", 0)
        if isinstance(analysis_result, dict)
        else 0
    )
    if not career_years and fallback_career_years:
        career_years = fallback_career_years

    skills_text = ", ".join(skills) if skills else "스킬 정보 없음"
    position_text = f"포지션: {position}" if position else ""

    content_preview = resume.content[:1000] if resume.content else ""
    experience_summary = resume.experience_summary or ""

    embedding_text = f"""이력서 원본:
{content_preview}

경력 요약:
{experience_summary}

보유 스킬: {skills_text}
{position_text}
""".strip()

    metadata = {
        "career_years": int(career_years or 0),
        "skills_count": len(skills),
        "position": position,
        "user_id": resume.user_id,
    }
    return embedding_text, metadata

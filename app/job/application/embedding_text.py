from __future__ import annotations

from job.models import JobPosting


def build_job_posting_embedding_text(job_posting: JobPosting) -> tuple[str, dict]:
    """
    채용 공고 임베딩용 텍스트와 메타데이터를 생성합니다.
    """
    skills_required = job_posting.skills_required or []
    skills_required_text = ", ".join(skills_required) if skills_required else "없음"

    career_text = (
        f"{job_posting.career_min}년 ~ {job_posting.career_max}년"
        if job_posting.career_min is not None and job_posting.career_max is not None
        else "경력 무관"
    )
    location_text = f"{job_posting.location}" + (
        f" ({job_posting.district})" if job_posting.district else ""
    )

    embedding_text = f"""
포지션: {job_posting.position or 'N/A'}
주요 업무:
{job_posting.main_tasks or 'N/A'}
자격 요건:
{job_posting.requirements or 'N/A'}
우대 사항:
{job_posting.preferred_points or 'N/A'}
필수 기술 스택: {skills_required_text}
경력 범위: {career_text}
지역: {location_text}
고용 형태: {job_posting.employment_type or 'N/A'}
""".strip()

    metadata = {
        "company_name": job_posting.company_name or "",
        "location": job_posting.location or "",
        "position": job_posting.position or "",
        "employment_type": job_posting.employment_type or "",
        "career_min": job_posting.career_min,
        "career_max": job_posting.career_max,
    }
    return embedding_text, metadata

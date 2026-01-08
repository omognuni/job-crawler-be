from __future__ import annotations

from job.models import JobPosting
from skill.services import SkillExtractionService


def normalize_position_text(text: str) -> str:
    if not text:
        return ""
    s = str(text).strip().lower()
    s = s.replace(" ", "").replace("/", "").replace("-", "").replace("_", "")
    return s


def map_position_to_category(normalized_text: str) -> str:
    if not normalized_text:
        return ""

    backend_keywords = ("backend", "백엔드", "server", "서버")
    frontend_keywords = ("frontend", "프론트", "web", "웹")
    devops_keywords = ("devops", "infra", "인프라", "sre", "platform", "플랫폼")
    data_ml_keywords = (
        "data",
        "ml",
        "ai",
        "머신러닝",
        "데이터",
        "research",
        "리서치",
    )
    mobile_keywords = ("android", "ios", "mobile", "모바일")

    if any(k in normalized_text for k in backend_keywords):
        return "backend"
    if any(k in normalized_text for k in frontend_keywords):
        return "frontend"
    if any(k in normalized_text for k in devops_keywords):
        return "devops"
    if any(k in normalized_text for k in data_ml_keywords):
        return "data_ml"
    if any(k in normalized_text for k in mobile_keywords):
        return "mobile"

    return ""


def calculate_position_similarity(user_position: str, job_position: str) -> float:
    if not user_position or not job_position:
        return 0.0

    u = normalize_position_text(user_position)
    j = normalize_position_text(job_position)
    if not u or not j:
        return 0.0

    u_cat = map_position_to_category(u)
    j_cat = map_position_to_category(j)
    if u_cat and j_cat:
        return 1.0 if u_cat == j_cat else 0.0

    if u == j:
        return 1.0
    if u in j or j in u:
        return 0.8

    return 0.0


def calculate_match_score_and_reason(
    *, posting: JobPosting, user_skills: set[str], user_career_years: int
) -> tuple[int, str]:
    """
    공고와 사용자 간의 rule-based 매칭 점수 및 사유 계산.
    - 기존 RecommendationService._calculate_match_score_and_reason 로직을 그대로 분리한 것입니다.
    """
    score = 0
    reasons: list[str] = []

    required_skills = set(posting.skills_required or [])
    if required_skills:
        matched_required = user_skills & required_skills
        required_match_ratio = len(matched_required) / len(required_skills)
        required_score = int(required_match_ratio * 50)
        score += required_score

        if required_match_ratio >= 0.7:
            reasons.append(
                f"필수 스킬 {len(matched_required)}/{len(required_skills)}개 보유"
            )
        elif required_match_ratio >= 0.4:
            reasons.append(f"필수 스킬 일부 보유 ({len(matched_required)}개)")

    if posting.skills_preferred:
        preferred_skills = set(
            SkillExtractionService.extract_skills(posting.skills_preferred)
        )
        if preferred_skills:
            matched_preferred = user_skills & preferred_skills
            preferred_match_ratio = len(matched_preferred) / len(preferred_skills)
            preferred_score = int(preferred_match_ratio * 30)
            score += preferred_score

            if matched_preferred:
                reasons.append(f"우대사항 {len(matched_preferred)}개 충족")

    career_min = posting.career_min
    career_max = posting.career_max

    if career_min <= user_career_years <= career_max:
        score += 20
        reasons.append(f"경력 요건 충족 ({user_career_years}년)")
    elif career_min <= user_career_years <= career_max + 2:
        score += 10
        reasons.append(f"경력 범위 근접 ({user_career_years}년)")

    match_reason = " | ".join(reasons) if reasons else "벡터 유사도 기반 매칭"
    score = min(score, 100)
    return score, match_reason

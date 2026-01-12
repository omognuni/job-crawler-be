from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from common.adapters.gemini_model_settings import get_gemini_model_name
from resume.models import Resume

logger = logging.getLogger(__name__)


class GeminiSearchPlanBuilder:
    """
    Gemini 기반 검색전략 플래너.
    - API 키가 없거나 실패하면 휴리스틱 fallback을 반환합니다.
    """

    def build_plan(self, *, resume: Resume) -> dict:
        # 테스트 환경(pytest)에서는 외부 LLM 호출을 절대 하지 않습니다.
        if os.getenv("PYTEST_CURRENT_TEST"):
            return self._fallback_plan(resume=resume)

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return self._fallback_plan(resume=resume)

        try:
            from google import genai
            from google.genai.types import GenerateContentConfig

            client = genai.Client(api_key=api_key)
            analysis_result = (
                resume.analysis_result
                if isinstance(resume.analysis_result, dict)
                else {}
            )
            position = str(analysis_result.get("position", "") or "").strip()
            career_years = int(analysis_result.get("career_years", 0) or 0)
            skills = analysis_result.get("skills", []) or []
            skills_text = ", ".join(skills) if isinstance(skills, list) else ""
            resume_summary = (
                resume.experience_summary or ""
            ).strip() or "이력서 요약 없음"

            prompt = f"""
너는 채용 추천 시스템의 '검색 전략 생성기'다.
목표: 사용자가 '지원하고 싶어질 만한' 공고를 찾기 위해, 벡터 검색 쿼리/필터/평가 루브릭을 JSON으로 생성해라.

[Resume Summary]
{resume_summary}
Skills: {skills_text}
Position(분석값): {position}
Career Years(분석값): {career_years}

규칙:
- 반드시 JSON만 출력.
- queries는 3~6개.
- 각 query는 text(문장)와 weight(0~1) 포함.
- filters에는 career_years 기반 필터를 포함하되, career_min은 '내 경력 + 3년'까지 허용하는 의도를 반영.
- scoring_rubric은 fit/skill_coverage/growth/risk 가중치 합이 1이 되게.

JSON 스키마(예시):
{{
  "target_role": "백엔드 개발자",
  "role_category": "backend|frontend|devops|data_ml|mobile|unknown",
  "seniority": "junior|mid|senior|unknown",
  "must_have_skills": ["..."],
  "nice_to_have_skills": ["..."],
  "avoid": ["..."],
  "queries": [{{"text":"...","weight":1.0}}],
  "filters": {{
    "career_years": {career_years},
    "career_min_slack_years": 3,
    "position_category": "backend|frontend|devops|data_ml|mobile|"
  }},
  "scoring_rubric": {{"fit":0.45,"skill_coverage":0.30,"growth":0.15,"risk":0.10}}
}}
""".strip()

            resp = client.models.generate_content(
                model=get_gemini_model_name(key="search_plan_builder"),
                contents=prompt,
                config=GenerateContentConfig(temperature=0.1, max_output_tokens=800),
            )
            text = (resp.text or "").strip()
            text = re.sub(r"^```json\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
            data: Any = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError("planner response is not a JSON object")
            return self._sanitize_plan(data, resume=resume)
        except Exception as e:
            logger.warning(f"GeminiSearchPlanBuilder failed - using fallback: {e}")
            return self._fallback_plan(resume=resume)

    def _sanitize_plan(self, plan: dict, *, resume: Resume) -> dict:
        """
        외부 입력(LLM)을 최소한으로 정규화합니다.
        """
        analysis_result = (
            resume.analysis_result if isinstance(resume.analysis_result, dict) else {}
        )
        career_years = int(analysis_result.get("career_years", 0) or 0)

        queries = plan.get("queries") or []
        if not isinstance(queries, list) or not queries:
            queries = []
        cleaned_queries: list[dict] = []
        for q in queries[:6]:
            if not isinstance(q, dict):
                continue
            text = str(q.get("text", "") or "").strip()
            if not text:
                continue
            try:
                weight = float(q.get("weight", 1.0))
            except Exception:
                weight = 1.0
            weight = min(max(weight, 0.0), 1.0)
            cleaned_queries.append({"text": text, "weight": weight})
        if not cleaned_queries:
            # 최소 3개는 확보
            cleaned_queries = self._fallback_plan(resume=resume)["queries"]

        filters = plan.get("filters") if isinstance(plan.get("filters"), dict) else {}
        filters = {
            **filters,
            "career_years": career_years,
            "career_min_slack_years": 3,
        }

        rubric = (
            plan.get("scoring_rubric")
            if isinstance(plan.get("scoring_rubric"), dict)
            else {}
        )
        fit = float(rubric.get("fit", 0.45) or 0.45)
        skill = float(rubric.get("skill_coverage", 0.30) or 0.30)
        growth = float(rubric.get("growth", 0.15) or 0.15)
        risk = float(rubric.get("risk", 0.10) or 0.10)
        s = fit + skill + growth + risk
        if s <= 0:
            fit, skill, growth, risk = 0.45, 0.30, 0.15, 0.10
            s = 1.0
        rubric = {
            "fit": fit / s,
            "skill_coverage": skill / s,
            "growth": growth / s,
            "risk": risk / s,
        }

        return {
            "target_role": str(plan.get("target_role", "") or "").strip(),
            "role_category": str(plan.get("role_category", "") or "").strip(),
            "seniority": str(plan.get("seniority", "") or "").strip(),
            "must_have_skills": plan.get("must_have_skills") or [],
            "nice_to_have_skills": plan.get("nice_to_have_skills") or [],
            "avoid": plan.get("avoid") or [],
            "queries": cleaned_queries,
            "filters": filters,
            "scoring_rubric": rubric,
        }

    def _fallback_plan(self, *, resume: Resume) -> dict:
        analysis_result = (
            resume.analysis_result if isinstance(resume.analysis_result, dict) else {}
        )
        position = str(analysis_result.get("position", "") or "").strip()
        career_years = int(analysis_result.get("career_years", 0) or 0)
        skills = analysis_result.get("skills", []) or []
        if not isinstance(skills, list):
            skills = []
        skills_top = [str(s).strip() for s in skills[:8] if str(s).strip()]
        skills_text = " ".join(skills_top)

        base = position or "개발자"
        queries = [
            {"text": f"{base} {skills_text}".strip(), "weight": 1.0},
            {"text": f"{skills_text} {base}".strip(), "weight": 0.8},
            {
                "text": f"{base} 주요 업무 자격 요건 {skills_text}".strip(),
                "weight": 0.6,
            },
        ]
        return {
            "target_role": base,
            "role_category": "unknown",
            "seniority": "unknown",
            "must_have_skills": skills_top,
            "nice_to_have_skills": [],
            "avoid": [],
            "queries": queries,
            "filters": {
                "career_years": career_years,
                "career_min_slack_years": 3,
                "position_category": "",
            },
            "scoring_rubric": {
                "fit": 0.45,
                "skill_coverage": 0.30,
                "growth": 0.15,
                "risk": 0.10,
            },
        }

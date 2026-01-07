from __future__ import annotations

import logging

from common.application.result import Err, Ok, Result
from common.ports.resume_analyzer import ResumeAnalyzerPort
from common.ports.resume_repo import ResumeRepositoryPort
from common.ports.vector_store import VectorStorePort
from django.utils import timezone
from resume.application.embedding_text import build_resume_embedding_text
from resume.application.position_inference import infer_position_from_skills
from resume.dtos import ProcessResumeResultDTO
from skill.services import SkillExtractionService

logger = logging.getLogger(__name__)


class ProcessResumeUseCase:
    """
    이력서 처리 유스케이스.

    - run_analysis=False 인 경우, LLM 분석은 수행하지 않고 "임베딩만" 갱신합니다.
      (Admin 재임베딩/벡터 검색 최신화 등)
    """

    def __init__(
        self,
        *,
        resume_repo: ResumeRepositoryPort,
        vector_store: VectorStorePort,
        resume_analyzer: ResumeAnalyzerPort,
    ):
        self._resume_repo = resume_repo
        self._vector_store = vector_store
        self._resume_analyzer = resume_analyzer

    def execute(
        self,
        *,
        resume_id: int,
        run_analysis: bool = True,
    ) -> Result[ProcessResumeResultDTO]:
        resume = self._resume_repo.get_by_id(resume_id)
        if not resume:
            return Err(code="NOT_FOUND", message=f"Resume {resume_id} not found")

        # 변경 감지(현재 content_hash는 '현재 내용 해시'라서 분석 시점 비교가 어려움)
        # 분석 시점의 해시를 별도로 저장해서 정확하게 감지합니다.
        current_hash = resume.calculate_hash()
        analyzed_hash = getattr(resume, "analyzed_content_hash", None)
        content_changed_since_analysis = analyzed_hash != current_hash

        analysis_result = resume.analysis_result or {}
        has_analysis = bool(analysis_result) and bool(resume.experience_summary)

        needs_analysis = run_analysis and (
            content_changed_since_analysis or not has_analysis
        )

        # 1) 스킬은 LLM 없이 추출 (분석/임베딩 모두에서 사용)
        skills = SkillExtractionService.extract_skills(resume.content or "")
        inferred_position = infer_position_from_skills(skills)

        analysis = None
        if needs_analysis:
            logger.info(f"Running resume analysis for resume {resume_id}")
            analysis = self._resume_analyzer.analyze(
                content=resume.content or "",
                skills=skills,
                inferred_position=inferred_position,
            )

            resume.analysis_result = {
                "skills": analysis.skills,
                "position": analysis.position,
                "career_years": analysis.career_years,
                "strengths": analysis.strengths,
            }
            resume.experience_summary = analysis.experience_summary
            resume.analyzed_at = timezone.now()
            resume.analyzed_content_hash = current_hash

            self._resume_repo.save(
                resume,
                update_fields=[
                    "analysis_result",
                    "experience_summary",
                    "analyzed_at",
                    "analyzed_content_hash",
                ],
            )

        # 2) 임베딩 갱신 (항상 수행: 벡터 검색 최신화 목적)
        embedding_text, metadata = build_resume_embedding_text(
            resume,
            fallback_skills=skills,
            fallback_position=inferred_position,
        )
        if len(embedding_text) <= 30:
            return Err(code="VALIDATION_ERROR", message="Embedding text too short")

        self._vector_store.upsert_text(
            collection_name="resumes",
            doc_id=str(resume.id),
            text=embedding_text,
            metadata=metadata,
        )

        # 3) 결과 조립
        if analysis:
            skills_count = len(analysis.skills)
            career_years = analysis.career_years
            position = analysis.position or ""
        else:
            ar = resume.analysis_result or {}
            skills_count = len(ar.get("skills", [])) if isinstance(ar, dict) else 0
            career_years = ar.get("career_years", 0) if isinstance(ar, dict) else 0
            position = ar.get("position", "") if isinstance(ar, dict) else ""

        return Ok(
            ProcessResumeResultDTO(
                success=True,
                resume_id=resume.id,
                user_id=resume.user_id,
                skills_count=skills_count,
                career_years=career_years,
                position=position,
            )
        )

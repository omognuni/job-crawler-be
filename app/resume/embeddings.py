import logging
from typing import Dict, List, Optional

from common.vector_db import vector_db_client
from resume.models import Resume

logger = logging.getLogger(__name__)


class ResumeEmbeddingService:
    """
    이력서 임베딩 서비스
    """

    @staticmethod
    def embed_resume(
        resume: Resume,
    ) -> bool:
        """
        이력서 분석 결과를 Vector DB에 임베딩합니다.

        Args:
            resume_id: 이력서 ID
            user_id: 사용자 ID
            analysis: 분석 결과 (experience_summary, career_years, skills 포함)

        Returns:
            성공 여부
        """
        experience_summary = resume.experience_summary

        if not experience_summary or len(experience_summary) <= 10:
            return False

        try:
            collection = vector_db_client.get_or_create_collection("resumes")
            vector_db_client.upsert_documents(
                collection=collection,
                documents=[experience_summary],
                metadatas=[
                    {
                        "career_years": resume.analysis_result.career_years,
                        "skills_count": len(resume.analysis_result.skills),
                        "user_id": resume.user_id,
                    }
                ],
                ids=[str(resume.id)],
            )
            logger.info(f"Embedded resume {resume.id} to Vector DB")
            return True
        except Exception as e:
            logger.warning(f"Failed to embed resume {resume_id} to Vector DB: {str(e)}")
            return False

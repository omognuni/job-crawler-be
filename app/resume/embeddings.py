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

        원본 content, experience_summary, 스킬 정보를 결합하여 풍부한 임베딩 텍스트를 생성합니다.

        Args:
            resume: 이력서 모델

        Returns:
            성공 여부
        """
        experience_summary = resume.experience_summary

        if not experience_summary or len(experience_summary) <= 10:
            return False

        try:
            # 스킬 정보 추출
            skills = (
                resume.analysis_result.get("skills", [])
                if resume.analysis_result
                else []
            )
            skills_text = ", ".join(skills) if skills else "스킬 정보 없음"

            # 원본 content의 앞부분 추출 (최대 1000자)
            content_preview = resume.content[:1000] if resume.content else ""

            # 임베딩 텍스트 구성: 원본 일부 + LLM 요약 + 스킬 정보
            embedding_text = f"""이력서 원본:
{content_preview}

경력 요약:
{experience_summary}

보유 스킬: {skills_text}
""".strip()

            collection = vector_db_client.get_or_create_collection("resumes")
            vector_db_client.upsert_documents(
                collection=collection,
                documents=[embedding_text],
                metadatas=[
                    {
                        "career_years": (
                            resume.analysis_result.get("career_years", 0)
                            if resume.analysis_result
                            else 0
                        ),
                        "skills_count": len(skills),
                        "user_id": resume.user_id,
                    }
                ],
                ids=[str(resume.id)],
            )
            logger.info(f"Embedded resume {resume.id} to Vector DB")
            return True
        except Exception as e:
            logger.warning(f"Failed to embed resume {resume.id} to Vector DB: {str(e)}")
            return False

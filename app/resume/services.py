"""
Resume Service

이력서 관리 서비스(Backward Compatibility 중심).

- CRUD는 기존 인터페이스를 유지합니다.
- 분석/임베딩/외부 시스템 연동은 유스케이스/어댑터로 이동했습니다.
"""

import logging
from typing import Dict, List, Optional

from common.adapters.chroma_vector_store import ChromaVectorStore
from common.adapters.django_resume_repo import DjangoResumeRepository
from common.adapters.google_genai_resume_analyzer import GoogleGenAIResumeAnalyzer
from common.application.result import Err, Ok
from django.db import transaction
from resume.application.position_inference import infer_position_from_skills
from resume.application.usecases.process_resume import ProcessResumeUseCase
from resume.dtos import ProcessResumeResultDTO, ResumeAnalysisResultDTO
from resume.models import Resume
from skill.services import SkillExtractionService

logger = logging.getLogger(__name__)


class ResumeService:
    """
    이력서 서비스

    이력서 CRUD 및 분석 로직을 처리합니다.
    """

    @staticmethod
    def get_resume(user_id: int) -> Optional[Resume]:
        """
        이력서 조회 (User ID 기준)
        1:N 관계이므로 가장 최근에 수정된 이력서를 반환합니다.

        Args:
            user_id: 사용자 ID

        Returns:
            Resume 객체 또는 None
        """
        try:
            return (
                Resume.objects.filter(user_id=user_id).order_by("-updated_at").first()
            )
        except Exception as e:
            logger.warning(f"Error fetching resume for user {user_id}: {e}")
            return None

    @staticmethod
    def get_resume_by_id(resume_id: int, user_id: int) -> Optional[Resume]:
        """
        이력서 조회 (Resume ID 및 User ID 기준)

        Args:
            resume_id: 이력서 ID
            user_id: 사용자 ID

        Returns:
            Resume 객체 또는 None
        """
        try:
            return Resume.objects.get(id=resume_id, user_id=user_id)
        except Resume.DoesNotExist:
            return None

    @staticmethod
    def get_all_resumes() -> List[Resume]:
        """
        모든 이력서 조회

        Returns:
            Resume 쿼리셋
        """
        return Resume.objects.all()

    @staticmethod
    def create_resume(data: Dict) -> Resume:
        """
        이력서 생성

        Args:
            data: 이력서 데이터 딕셔너리

        Returns:
            생성된 Resume 객체
        """
        with transaction.atomic():
            resume = Resume.objects.create(**data)
            logger.info(f"Created Resume {resume.id} for user {resume.user_id}")
            return resume

    @staticmethod
    def update_resume(resume_id: int, user_id: int, data: Dict) -> Optional[Resume]:
        """
        이력서 업데이트

        Args:
            resume_id: 이력서 ID
            user_id: 사용자 ID
            data: 업데이트할 데이터 딕셔너리

        Returns:
            업데이트된 Resume 객체 또는 None
        """
        resume = ResumeService.get_resume_by_id(resume_id, user_id)
        if not resume:
            return None

        with transaction.atomic():
            for key, value in data.items():
                setattr(resume, key, value)
            resume.save()
            resume.refresh_from_db()
            logger.info(f"Updated Resume {resume_id} for user {user_id}")
            return resume

    @staticmethod
    def delete_resume(resume_id: int, user_id: int) -> bool:
        """
        이력서 삭제

        Args:
            resume_id: 이력서 ID
            user_id: 사용자 ID

        Returns:
            삭제 성공 여부
        """
        resume = ResumeService.get_resume_by_id(resume_id, user_id)
        if not resume:
            return False

        with transaction.atomic():
            resume.delete()
            logger.info(f"Deleted Resume {resume_id} for user {user_id}")
            return True

    @staticmethod
    def _analyze_resume_with_llm(content: str) -> ResumeAnalysisResultDTO:
        """
        [Deprecated] 기존 테스트/호환을 위해 유지합니다.
        실제 구현은 `GoogleGenAIResumeAnalyzer` 어댑터로 이동했습니다.
        """
        skills = SkillExtractionService.extract_skills(content)
        inferred_position = infer_position_from_skills(skills)
        return GoogleGenAIResumeAnalyzer().analyze(
            content=content,
            skills=skills,
            inferred_position=inferred_position,
        )

    @staticmethod
    def _infer_position_from_skills(skills: List[str]) -> str:
        """[Deprecated] 기존 인터페이스 유지."""
        return infer_position_from_skills(skills)

    @staticmethod
    def process_resume_sync(
        resume_id: int, force_reindex: bool = False
    ) -> ProcessResumeResultDTO:
        """
        이력서 처리 (동기 방식)

        [Backward Compatibility]
        내부 구현은 유스케이스로 이동했습니다.

        Args:
            resume_id: 이력서 ID (기존 user_id에서 변경됨)
            force_reindex: 강제 재인덱싱 여부 (True일 경우 분석 없이 임베딩만 갱신)

        Returns:
            ProcessResumeResultDTO: 처리 결과
        """
        usecase = ProcessResumeUseCase(
            resume_repo=DjangoResumeRepository(),
            vector_store=ChromaVectorStore(),
            resume_analyzer=GoogleGenAIResumeAnalyzer(),
        )
        result = usecase.execute(resume_id=resume_id, run_analysis=not force_reindex)
        if isinstance(result, Ok):
            return result.value
        assert isinstance(result, Err)
        return ProcessResumeResultDTO(success=False, error=result.message)

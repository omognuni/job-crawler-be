from __future__ import annotations

from common.adapters.chroma_vector_store import ChromaVectorStore
from common.adapters.django_resume_repo import DjangoResumeRepository
from common.adapters.google_genai_resume_analyzer import GoogleGenAIResumeAnalyzer
from resume.application.usecases.process_resume import ProcessResumeUseCase


def build_process_resume_usecase() -> ProcessResumeUseCase:
    """
    Resume 유스케이스 조립(Dependency Injection).
    - services/tasks/views에서는 이 함수만 통해 유스케이스를 얻도록 통일합니다.
    """
    return ProcessResumeUseCase(
        resume_repo=DjangoResumeRepository(),
        vector_store=ChromaVectorStore(),
        resume_analyzer=GoogleGenAIResumeAnalyzer(),
    )

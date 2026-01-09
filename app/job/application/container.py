from __future__ import annotations

from common.adapters.chroma_vector_store import ChromaVectorStore
from common.adapters.django_job_repo import DjangoJobPostingRepository
from common.adapters.neo4j_graph_store import Neo4jGraphStore
from job.application.usecases.process_job_posting import ProcessJobPostingUseCase


def build_process_job_posting_usecase() -> ProcessJobPostingUseCase:
    """
    Job 유스케이스 조립(Dependency Injection).
    """
    return ProcessJobPostingUseCase(
        job_repo=DjangoJobPostingRepository(),
        vector_store=ChromaVectorStore(),
        graph_store=Neo4jGraphStore(),
    )

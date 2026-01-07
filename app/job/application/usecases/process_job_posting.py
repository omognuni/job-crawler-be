from __future__ import annotations

import logging

from common.application.result import Err, Ok, Result
from common.ports.graph_store import GraphStorePort
from common.ports.job_repo import JobPostingRepositoryPort
from common.ports.vector_store import VectorStorePort
from job.application.embedding_text import build_job_posting_embedding_text
from skill.services import SkillExtractionService

logger = logging.getLogger(__name__)


class ProcessJobPostingUseCase:
    """
    채용 공고 처리 유스케이스.

    - 스킬 추출(필수/우대)
    - 임베딩 업서트(Chroma)
    - 그래프 업데이트(Neo4j)
    """

    def __init__(
        self,
        *,
        job_repo: JobPostingRepositoryPort,
        vector_store: VectorStorePort,
        graph_store: GraphStorePort,
    ):
        self._job_repo = job_repo
        self._vector_store = vector_store
        self._graph_store = graph_store

    def execute(self, *, posting_id: int) -> Result[dict]:
        job_posting = self._job_repo.get_by_id(posting_id)
        if not job_posting:
            return Err(code="NOT_FOUND", message=f"JobPosting {posting_id} not found")

        # 1) 스킬 추출
        skills_required, skills_preferred = (
            SkillExtractionService.extract_skills_from_job_posting(
                requirements=job_posting.requirements,
                preferred_points=job_posting.preferred_points,
                main_tasks=job_posting.main_tasks,
            )
        )

        # 2) 스킬 필드 업데이트(변경 시에만)
        if (
            job_posting.skills_required != skills_required
            or job_posting.skills_preferred != skills_preferred
        ):
            job_posting.skills_required = skills_required
            job_posting.skills_preferred = skills_preferred
            self._job_repo.save(
                job_posting, update_fields=["skills_required", "skills_preferred"]
            )

        # 3) 임베딩 업서트
        embedding_text, metadata = build_job_posting_embedding_text(job_posting)
        if len(embedding_text) > 10:
            self._vector_store.upsert_text(
                collection_name="job_postings",
                doc_id=str(posting_id),
                text=embedding_text,
                metadata=metadata,
            )
        else:
            logger.warning(f"Embedding text too short for posting {posting_id}")

        # 4) 그래프 업데이트
        if skills_required:
            self._graph_store.upsert_job_posting(
                posting_id=posting_id,
                position=job_posting.position,
                company_name=job_posting.company_name,
                skills_required=skills_required,
            )

        return Ok(
            {
                "success": True,
                "posting_id": posting_id,
                "skills_required": len(skills_required),
                "skills_preferred_text": (
                    skills_preferred[:50] if skills_preferred else ""
                ),
            }
        )

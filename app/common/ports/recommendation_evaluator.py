from __future__ import annotations

from typing import Optional, Protocol

from job.models import JobPosting
from recommendation.models import RecommendationPrompt
from resume.models import Resume


class RecommendationEvaluatorPort(Protocol):
    def evaluate_batch(
        self,
        *,
        postings: list[JobPosting],
        resume: Resume,
        prompt: RecommendationPrompt,
        search_contexts: Optional[list[dict]] = None,
    ) -> list[dict]: ...

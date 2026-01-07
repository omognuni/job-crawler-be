from __future__ import annotations

from typing import Protocol

from resume.dtos import ResumeAnalysisResultDTO


class ResumeAnalyzerPort(Protocol):
    def analyze(
        self,
        *,
        content: str,
        skills: list[str],
        inferred_position: str,
    ) -> ResumeAnalysisResultDTO: ...

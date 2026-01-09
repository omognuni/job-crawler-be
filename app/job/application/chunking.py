from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class JobPostingChunk:
    section: str
    chunk_index: int
    text: str


def _normalize_whitespace(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _split_into_sentences(text: str) -> list[str]:
    """
    한국어/영어 혼합 텍스트에서 대략적인 문장 단위로 분리합니다.
    - 완벽한 문장 분리는 목표가 아니고, "근거 스니펫" 품질을 높이는 것이 목적입니다.
    """
    t = _normalize_whitespace(text)
    if not t:
        return []

    # 문장 구분자로 흔한 패턴(.!?/다./요./함./니다.) 뒤에서 쪼갬
    # 너무 짧게 쪼개지 않도록 후처리에서 병합합니다.
    parts = re.split(r"(?<=[\.\!\?\n])\s+|(?<=다\.)\s+|(?<=요\.)\s+|(?<=니다\.)\s+", t)
    return [p.strip() for p in parts if p and p.strip()]


def chunk_text_for_rag(
    *,
    section: str,
    text: str,
    max_chars: int = 450,
    min_chars: int = 80,
) -> list[JobPostingChunk]:
    """
    RAG용 chunk 생성.
    - 문장 단위로 쪼갠 뒤, max_chars를 넘지 않도록 누적
    - 너무 짧은 chunk는 인접 chunk와 병합
    """
    sentences = _split_into_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    buf = ""
    for s in sentences:
        if not buf:
            buf = s
            continue

        candidate = f"{buf} {s}"
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            chunks.append(buf)
            buf = s
    if buf:
        chunks.append(buf)

    # 너무 짧은 chunk 병합
    merged: list[str] = []
    for c in chunks:
        if not merged:
            merged.append(c)
            continue
        if len(merged[-1]) < min_chars:
            merged[-1] = f"{merged[-1]} {c}".strip()
        else:
            merged.append(c)

    results: list[JobPostingChunk] = []
    for idx, c in enumerate(merged):
        c = _normalize_whitespace(c)
        if c:
            results.append(JobPostingChunk(section=section, chunk_index=idx, text=c))
    return results

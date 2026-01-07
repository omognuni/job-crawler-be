from __future__ import annotations

from typing import Any, Optional, Protocol


class VectorStorePort(Protocol):
    def upsert_text(
        self,
        *,
        collection_name: str,
        doc_id: str,
        text: str,
        metadata: dict,
    ) -> None: ...

    def get_embedding(self, *, collection_name: str, doc_id: str) -> Optional[Any]: ...

    def query_by_embedding(
        self,
        *,
        collection_name: str,
        query_embedding: Any,
        n_results: int = 5,
        min_similarity: Optional[float] = None,
        where: Optional[dict] = None,
    ) -> dict: ...

    def query_by_text(
        self,
        *,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        min_similarity: Optional[float] = None,
        where: Optional[dict] = None,
    ) -> dict: ...

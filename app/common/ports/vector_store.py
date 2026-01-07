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

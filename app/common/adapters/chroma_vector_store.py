from __future__ import annotations

from typing import Any, Optional

from common.vector_db import vector_db_client


class ChromaVectorStore:
    """
    ChromaDB(Vector DB) 어댑터.

    - 내부적으로는 기존 `common.vector_db.vector_db_client`를 그대로 사용합니다.
    - 유스케이스 레이어는 ChromaDB를 직접 알지 않고 이 어댑터(=VectorStorePort 구현)만 의존합니다.
    """

    def upsert_text(
        self,
        *,
        collection_name: str,
        doc_id: str,
        text: str,
        metadata: dict,
    ) -> None:
        collection = vector_db_client.get_or_create_collection(collection_name)
        vector_db_client.upsert_documents(
            collection=collection,
            documents=[text],
            metadatas=[metadata],
            ids=[doc_id],
        )

    def get_embedding(self, *, collection_name: str, doc_id: str) -> Optional[Any]:
        collection = vector_db_client.get_or_create_collection(collection_name)
        result = collection.get(ids=[doc_id], include=["embeddings"])
        if not result:
            return None
        embeddings = result.get("embeddings")
        if embeddings is None:
            return None
        try:
            return embeddings[0] if len(embeddings) > 0 else None
        except Exception:
            # 임베딩 타입이 특이한 경우는 그대로 반환(호출자가 처리)
            return embeddings

    def query_by_embedding(
        self,
        *,
        collection_name: str,
        query_embedding: Any,
        n_results: int = 5,
        min_similarity: Optional[float] = None,
        where: Optional[dict] = None,
    ) -> dict:
        collection = vector_db_client.get_or_create_collection(collection_name)
        # vector_db_client.query_by_embedding은 "리스트 형태" 임베딩을 기대합니다.
        return vector_db_client.query_by_embedding(
            collection=collection,
            query_embeddings=[query_embedding],
            n_results=n_results,
            min_similarity=min_similarity,
            where=where,
        )

    def query_by_text(
        self,
        *,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        min_similarity: Optional[float] = None,
        where: Optional[dict] = None,
    ) -> dict:
        collection = vector_db_client.get_or_create_collection(collection_name)
        return vector_db_client.query(
            collection=collection,
            query_texts=[query_text],
            n_results=n_results,
            min_similarity=min_similarity,
            where=where,
        )

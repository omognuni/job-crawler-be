import chromadb
from chromadb.utils import embedding_functions


class VectorDB:
    def __init__(self, host="chromadb", port=8000):
        self.client = chromadb.HttpClient(host=host, port=port)
        self.embedding_function = (
            embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="paraphrase-multilingual-MiniLM-L12-v2"
            )
        )

    def get_or_create_collection(self, name):
        return self.client.get_or_create_collection(
            name=name, embedding_function=self.embedding_function
        )

    def upsert_documents(self, collection, documents, metadatas, ids):
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

    def query(
        self, collection, query_texts, n_results=5, min_similarity=None, where=None
    ):
        """
        벡터 검색 쿼리 수행

        Args:
            collection: ChromaDB collection 객체
            query_texts: 쿼리 텍스트 리스트
            n_results: 반환할 결과 수
            min_similarity: 최소 유사도 임계값 (None이면 적용 안 함)
                           ChromaDB는 distance를 반환하므로, distance <= (1 - min_similarity)로 변환
            where: 메타데이터 필터 딕셔너리 (예: {"career_min": {"$lte": 5}})

        Returns:
            검색 결과 딕셔너리 (ids, distances, documents, metadatas 포함)
        """
        query_kwargs = {
            "query_texts": query_texts,
            "n_results": n_results,
            # RAG 근거 구성을 위해 documents/metadatas가 필요합니다.
            # 기존 호출자들은 ids/distances만 사용하므로 include를 넓혀도 호환됩니다.
            "include": ["distances", "documents", "metadatas"],
        }

        if where:
            query_kwargs["where"] = where

        results = collection.query(**query_kwargs)

        # 유사도 임계값 적용
        if min_similarity is not None and results.get("ids") and results["ids"][0]:
            # ChromaDB는 cosine distance를 반환 (0=유사, 2=다름)
            # similarity = 1 - (distance / 2)로 변환 가능
            # 또는 직접 distance <= (1 - min_similarity) * 2 사용
            # 여기서는 distance 기준으로 필터링 (작을수록 유사)
            max_distance = (1 - min_similarity) * 2  # similarity 0.7 -> distance 0.6

            filtered_ids = []
            filtered_distances = []
            filtered_documents = []
            filtered_metadatas = []

            distances = results["distances"][0] if results.get("distances") else []
            ids = results["ids"][0]
            documents = (
                results.get("documents", [[]])[0] if results.get("documents") else []
            )
            metadatas = (
                results.get("metadatas", [[]])[0] if results.get("metadatas") else []
            )

            for idx, distance in enumerate(distances):
                if distance <= max_distance:
                    filtered_ids.append(ids[idx])
                    filtered_distances.append(distance)
                    if documents:
                        filtered_documents.append(
                            documents[idx] if idx < len(documents) else None
                        )
                    if metadatas:
                        filtered_metadatas.append(
                            metadatas[idx] if idx < len(metadatas) else None
                        )

            results = {
                "ids": [filtered_ids],
                "distances": [filtered_distances],
                "documents": [filtered_documents] if filtered_documents else None,
                "metadatas": [filtered_metadatas] if filtered_metadatas else None,
            }

        return results

    def query_by_embedding(
        self, collection, query_embeddings, n_results=5, min_similarity=None, where=None
    ):
        """
        임베딩 벡터로 직접 검색

        Args:
            collection: ChromaDB collection 객체
            query_embeddings: 쿼리 임베딩 벡터 리스트
            n_results: 반환할 결과 수
            min_similarity: 최소 유사도 임계값
            where: 메타데이터 필터 딕셔너리

        Returns:
            검색 결과 딕셔너리
        """
        query_kwargs = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
            "include": ["distances", "documents", "metadatas"],
        }

        if where:
            query_kwargs["where"] = where

        results = collection.query(**query_kwargs)

        # 유사도 임계값 적용
        if min_similarity is not None and results.get("ids") and results["ids"][0]:
            max_distance = (1 - min_similarity) * 2

            filtered_ids = []
            filtered_distances = []
            filtered_documents = []
            filtered_metadatas = []

            distances = results["distances"][0] if results.get("distances") else []
            ids = results["ids"][0]
            documents = (
                results.get("documents", [[]])[0] if results.get("documents") else []
            )
            metadatas = (
                results.get("metadatas", [[]])[0] if results.get("metadatas") else []
            )

            for idx, distance in enumerate(distances):
                if distance <= max_distance:
                    filtered_ids.append(ids[idx])
                    filtered_distances.append(distance)
                    if documents:
                        filtered_documents.append(
                            documents[idx] if idx < len(documents) else None
                        )
                    if metadatas:
                        filtered_metadatas.append(
                            metadatas[idx] if idx < len(metadatas) else None
                        )

            results = {
                "ids": [filtered_ids],
                "distances": [filtered_distances],
                "documents": [filtered_documents] if filtered_documents else None,
                "metadatas": [filtered_metadatas] if filtered_metadatas else None,
            }

        return results


# Singleton instance
vector_db_client = VectorDB(host="chromadb", port=8000)

import chromadb
from chromadb.utils import embedding_functions


class VectorDB:
    def __init__(self, host="chromadb", port=8000):
        self.client = chromadb.HttpClient(host=host, port=port)
        self.embedding_function = (
            embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
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

    def query(self, collection, query_texts, n_results=5):
        return collection.query(
            query_texts=query_texts,
            n_results=n_results,
        )


# Singleton instance
vector_db_client = VectorDB(host="chromadb", port=8000)

import os

import chromadb


def check_chroma_data():
    try:
        # ChromaDB 클라이언트 연결 (Docker 내부에서 실행 가정)
        client = chromadb.HttpClient(host="chromadb", port=8000)

        print("Successfully connected to ChromaDB.")

        collections = client.list_collections()
        print(f"Found {len(collections)} collections.")

        total_documents = 0
        for collection in collections:
            count = collection.count()
            print(f"- Collection: {collection.name}, Documents: {count}")
            total_documents += count

        if total_documents == 0:
            print("\n⚠️  No documents found in ChromaDB.")
        else:
            print(f"\n✅ Total documents found: {total_documents}")

    except Exception as e:
        print(f"❌ Error connecting to ChromaDB: {e}")


if __name__ == "__main__":
    check_chroma_data()

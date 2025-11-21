### `common` App Summary

The `common` app provides shared utility services for other applications within the project, primarily focusing on database integrations for advanced functionalities like graph-based relationships and vector-based semantic search. It encapsulates the logic for interacting with Neo4j (graph database) and ChromaDB (vector database).

**Key Functionality:**
*   **Graph Database Client (`graph_db.py`):**
    *   Manages connections and interactions with a Neo4j database.
    *   Stores and relates `JobPosting`, `Company`, and `Skill` entities.
    *   Supports operations like adding job postings with skills, finding related jobs based on skills, filtering job postings by skill matching (used in hybrid search), and retrieving skill statistics.
    *   Crucial for establishing and leveraging skill-based relationships in the recommendation system.
*   **Vector Database Client (`vector_db.py`):**
    *   Manages connections and interactions with a ChromaDB vector database.
    *   Utilizes a Sentence Transformer model ("all-MiniLM-L6-v2") to generate embeddings for text data.
    *   Provides functionalities for creating/retrieving collections, upserting documents (text content, metadata, IDs), and performing similarity searches based on vector embeddings.
    *   Essential for semantic search and vector-based recommendation aspects.
*   **Singleton Instances:** Both `GraphDBClient` and `VectorDB` are implemented as singletons (`graph_db_client`, `vector_db_client`) to ensure efficient resource management and consistent configuration across the application.

**URLs:**
None. The `common` app provides internal services and does not expose direct API endpoints.

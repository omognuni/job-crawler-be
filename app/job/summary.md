### `job` App Summary

The `job` app is responsible for managing job postings, user resumes, and providing job recommendation functionalities. It integrates with both vector databases (ChromaDB) for semantic search and graph databases (Neo4j) for skill-based relationships to deliver a hybrid recommendation system.

**Key Functionality:**
*   **Job Posting Management:** Stores and manages details of job openings, including skills required and preferred.
*   **Resume Management:** Handles user resume content, tracks changes, and performs analysis to extract skills, career years, and experience summaries.
*   **Skill Extraction:** An LLM-Free module that uses regular expression matching to identify technical skills from text, crucial for both job postings and resumes.
*   **Hybrid Job Recommendation Engine:** Provides real-time job recommendations by combining vector similarity search (from resume embeddings to job posting embeddings) and skill graph matching (using Neo4j). It calculates a match score and provides reasons for each recommendation.
*   **Asynchronous Processing:** Utilizes Celery tasks to process job postings (extract skills, generate embeddings, update graph DB) and resumes (analyze content, extract features with LLM, generate embeddings) in the background.
*   **Job Search:** Allows searching job postings using a vector-based similarity search.
*   **Skill-based Job Retrieval:** Enables fetching job postings related to a particular skill from the graph database.

**URLs:**
*   **Job Postings:**
    *   `GET /api/v1/job-postings/`: List all job postings.
    *   `POST /api/v1/job-postings/`: Create a new job posting.
    *   `GET /api/v1/job-postings/<id>/`: Retrieve a specific job posting.
    *   `PUT /api/v1/job-postings/<id>/`: Update a specific job posting.
    *   `PATCH /api/v1/job-postings/<id>/`: Partially update a specific job posting.
    *   `DELETE /api/v1/job-postings/<id>/`: Delete a specific job posting.
*   **Resumes:**
    *   `GET /api/v1/resumes/`: List all resumes.
    *   `POST /api/v1/resumes/`: Create a new resume.
    *   `GET /api/v1/resumes/<id>/`: Retrieve a specific resume.
    *   `PUT /api/v1/resumes/<id>/`: Update a specific resume.
    *   `PATCH /api/v1/resumes/<id>/`: Partially update a specific resume.
    *   `DELETE /api/v1/resumes/<id>/`: Delete a specific resume.
*   **Job Recommendations (CRUD & Real-time):**
    *   `GET /api/v1/recommendations/`: List all job recommendations (can be filtered by `user_id`).
    *   `POST /api/v1/recommendations/`: Create a new job recommendation.
    *   `GET /api/v1/recommendations/<id>/`: Retrieve a specific job recommendation.
    *   `PUT /api/v1/recommendations/<id>/`: Update a specific job recommendation.
    *   `PATCH /api/v1/recommendations/<id>/`: Partially update a specific job recommendation.
    *   `DELETE /api/v1/recommendations/<id>/`: Delete a specific job recommendation.
    *   `GET /api/v1/recommendations/for-user/<user_id>/`: Generate and retrieve real-time job recommendations for a given user.
*   **Job Search:**
    *   `GET /api/v1/search/?query=<str>`: Search job postings by query text using vector similarity.
*   **Related Jobs by Skill:**
    *   `GET /api/v1/related-by-skill/<str:skill_name>/`: Retrieve job postings that require a specified skill.
*   **Real-time Recommendations (Redundant):**
    *   `GET /api/v1/recommend/?user_id=<int>&limit=<int>`: Another endpoint for real-time job recommendations for a user. (Note: This endpoint appears redundant with `/api/v1/recommendations/for-user/<user_id>/`).

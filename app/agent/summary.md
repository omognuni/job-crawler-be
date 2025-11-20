### `agent` App Summary

The `agent` app currently provides the infrastructure for a `CrewAI`-based multi-agent system, specifically for an **(now deprecated for primary use)** job recommendation workflow. While the core real-time job recommendation functionality has moved to the `job` app (using an "AI-Free" engine for performance and cost), the `agent` app's components illustrate a complex AI-driven process involving resume analysis, intelligent job posting search, and recommendation ranking. This app might be repurposed for other AI functionalities in the future.

**Key Functionality (as designed for the CrewAI workflow):**
*   **Multi-Agent System:** Utilizes `crewai` to define and orchestrate multiple specialized agents (`resume_inspector`, `job_posting_inspector`, `job_hunter`).
*   **Resume Analysis (Agent-driven):** An agent (via `get_resume_tool`) is designed to analyze user resumes, extracting structured information like skills, career years, and strengths.
*   **Intelligent Job Posting Search (Agent-driven):** An agent (via `hybrid_search_job_postings_tool`) performs a sophisticated job posting search using a hybrid approach (vector similarity from ChromaDB + skill matching from Neo4j).
*   **Recommendation Ranking & Saving (Agent-driven):** An agent (via `save_recommendations_tool`) processes resume analysis results and fetched job postings to calculate match scores, rank jobs, and save the top recommendations.
*   **Custom Tools:** Provides custom `crewai` tools (`vector_search_job_postings_tool`, `hybrid_search_job_postings_tool`, `get_resume_tool`, `analyze_resume_tool`, `save_recommendations_tool`) to bridge agents with application data and external services (PostgreSQL, ChromaDB, Neo4j).

**Deprecation Note:** The primary job recommendation logic implemented through this `crew` (`JobHunterCrew`) has been replaced by a more efficient, AI-Free engine in the `job` app (`job.recommender.py`).

**URLs:**
None. The `agent` app does not expose direct API endpoints. Its functionalities are intended for internal use by the multi-agent system or other application components.

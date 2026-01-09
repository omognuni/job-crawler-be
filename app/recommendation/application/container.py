from __future__ import annotations

from common.adapters.chroma_vector_store import ChromaVectorStore
from common.adapters.gemini_recommendation_evaluator import (
    GeminiRecommendationEvaluator,
)
from common.adapters.neo4j_graph_store import Neo4jGraphStore
from recommendation.application.usecases.generate_recommendations import (
    GenerateRecommendationsUseCase,
)


def build_generate_recommendations_usecase() -> GenerateRecommendationsUseCase:
    """
    Recommendation 유스케이스 조립(Dependency Injection).
    """
    return GenerateRecommendationsUseCase(
        vector_store=ChromaVectorStore(),
        graph_store=Neo4jGraphStore(),
        evaluator=GeminiRecommendationEvaluator(),
    )

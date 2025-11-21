"""
Search Views

검색 관련 API 뷰
"""

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import SearchService


class JobSearchView(APIView):
    """
    벡터 유사도 기반 채용 공고 검색

    ChromaDB를 사용하여 의미론적 유사도 검색을 수행합니다.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="query",
                description="검색 쿼리 텍스트",
                required=True,
                type=OpenApiTypes.STR,
            ),
            OpenApiParameter(
                name="limit",
                description="결과 수 (기본 20)",
                required=False,
                type=OpenApiTypes.INT,
            ),
        ],
        responses={
            200: OpenApiTypes.OBJECT,  # Or define a specific serializer for search results
        },
        summary="Vector Search",
        description="Search job postings using vector similarity.",
    )
    def get(self, request):
        query = request.query_params.get("query")
        if not query:
            return Response({"error": "Query parameter is required"}, status=400)

        limit = int(request.query_params.get("limit", 20))

        # 검색 서비스 호출
        results = SearchService.vector_search(query, n_results=limit)

        return Response(results)


class HybridSearchView(APIView):
    """
    하이브리드 검색 (Vector + Graph)

    벡터 유사도와 스킬 매칭을 결합한 2단계 검색을 수행합니다.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        request=OpenApiTypes.OBJECT,  # Or define a serializer for the request body
        responses={
            200: OpenApiTypes.OBJECT,
        },
        summary="Hybrid Search",
        description="Search job postings using both vector similarity and skill matching.",
    )
    def post(self, request):
        query = request.data.get("query")
        skills = request.data.get("skills", [])
        limit = int(request.data.get("limit", 20))

        if not query:
            return Response({"error": "Query parameter is required"}, status=400)

        if not isinstance(skills, list):
            return Response({"error": "Skills must be a list"}, status=400)

        # 하이브리드 검색 서비스 호출
        results = SearchService.hybrid_search(query, skills, n_results=limit)

        return Response(
            {
                "query": query,
                "skills": skills,
                "count": len(results),
                "results": results,
            }
        )

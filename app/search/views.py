"""
Search Views

검색 관련 API 뷰
"""

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

    def get(self, request):
        """
        GET /api/v1/search/?query=<text>&limit=<int>

        Args:
            query: 검색 쿼리 텍스트 (필수)
            limit: 결과 수 (선택, 기본 20)

        Returns:
            검색된 채용 공고 리스트
        """
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

    def post(self, request):
        """
        POST /api/v1/search/hybrid/

        Body:
            query: 검색 쿼리 텍스트
            skills: 사용자 보유 스킬 리스트
            limit: 결과 수 (선택, 기본 20)

        Returns:
            스킬 매칭된 채용 공고 리스트
        """
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

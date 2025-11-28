"""
Recommendation Views

추천 API 엔드포인트 (Thin Controller)
"""

import logging
import time

from recommendation.models import JobRecommendation, RecommendationPrompt
from recommendation.serializers import (
    JobRecommendationReadSerializer,
    JobRecommendationWriteSerializer,
    RecommendationPromptSerializer,
)
from recommendation.services import RecommendationService
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

logger = logging.getLogger(__name__)


class JobRecommendationViewSet(ModelViewSet):
    """
    채용 공고 추천 ViewSet (Thin Controller)

    비즈니스 로직은 RecommendationService에 위임하고,
    HTTP 요청/응답 처리만 담당합니다.
    """

    queryset = JobRecommendation.objects.all()

    def get_serializer_class(self):
        """
        action에 따라 적절한 Serializer 반환

        - 읽기 작업 (list, retrieve): JobRecommendationReadSerializer
        - 쓰기 작업 (create, update, partial_update): JobRecommendationWriteSerializer
        """
        if self.action in ["create", "update", "partial_update"]:
            return JobRecommendationWriteSerializer
        return JobRecommendationReadSerializer

    def list(self, request, *args, **kwargs):
        """
        저장된 추천 목록 조회

        GET /api/v1/recommendations/?user_id=<int>
        """
        user_id = request.query_params.get("user_id")

        if user_id:
            try:
                user_id = int(user_id)
                recommendations = RecommendationService.get_recommendations_by_user(
                    user_id
                )
                serializer = self.get_serializer(recommendations, many=True)
                return Response(serializer.data)
            except ValueError:
                return Response(
                    {"error": "user_id must be an integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                logger.error(
                    f"Failed to list recommendations for user {user_id}: {str(e)}",
                    exc_info=True,
                )
                return Response(
                    {"error": "Failed to retrieve recommendations"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # user_id 없으면 전체 조회
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, pk=None, *args, **kwargs):
        """
        추천 상세 조회

        GET /api/v1/recommendations/<id>/
        """
        try:
            recommendation = RecommendationService.get_recommendation(int(pk))
            if not recommendation:
                return Response(
                    {"error": "Recommendation not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = self.get_serializer(recommendation)
            return Response(serializer.data)
        except Exception as e:
            logger.error(
                f"Failed to retrieve recommendation {pk}: {str(e)}", exc_info=True
            )
            return Response(
                {"error": "Failed to retrieve recommendation"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def create(self, request, *args, **kwargs):
        """
        추천 생성

        POST /api/v1/recommendations/
        """
        try:
            # Write Serializer로 데이터 검증
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            recommendation = RecommendationService.create_recommendation(
                serializer.validated_data
            )

            # Read Serializer로 응답 반환
            response_serializer = JobRecommendationReadSerializer(recommendation)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Failed to create recommendation: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to create recommendation"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, pk=None, *args, **kwargs):
        """
        추천 삭제

        DELETE /api/v1/recommendations/<id>/
        """
        try:
            success = RecommendationService.delete_recommendation(int(pk))
            if not success:
                return Response(
                    {"error": "Recommendation not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(
                f"Failed to delete recommendation {pk}: {str(e)}", exc_info=True
            )
            return Response(
                {"error": "Failed to delete recommendation"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="for-resume/(?P<resume_id>[0-9]+)")
    def for_resume(self, request, resume_id=None):
        """
        특정 이력서를 위한 실시간 추천 생성

        GET /api/v1/recommendations/for-resume/<resume_id>/?limit=10

        Args:
            resume_id: 이력서 ID (URL 파라미터)
            limit: 반환할 추천 개수 (쿼리 파라미터, 기본값 10)

        Returns:
            실시간 생성된 추천 공고 리스트
        """
        start_time = time.time()

        try:
            resume_id = int(resume_id)
            limit = int(request.query_params.get("limit", 10))
            prompt_id = request.query_params.get("prompt_id")
            if prompt_id:
                prompt_id = int(prompt_id)
        except ValueError:
            return Response(
                {"error": "resume_id and limit must be integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 실시간 추천 생성
            recommendations = RecommendationService.get_recommendations(
                resume_id, limit=limit, prompt_id=prompt_id
            )

            # 응답 시간 로깅
            elapsed_time = time.time() - start_time
            logger.info(
                f"Generated {len(recommendations)} recommendations for resume {resume_id} "
                f"in {elapsed_time:.3f} seconds"
            )

            serializer = self.get_serializer(recommendations, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(
                f"Failed to generate recommendations for resume {resume_id}: {str(e)}",
                exc_info=True,
            )
            return Response(
                {"error": "Failed to generate recommendations"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RecommendationPromptViewSet(GenericViewSet, ListModelMixin):
    """
    추천 프롬프트 ViewSet
    """

    queryset = RecommendationPrompt.objects.all()
    serializer_class = RecommendationPromptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """활성화된 프롬프트만 조회"""
        return RecommendationPrompt.objects.filter(is_active=True)

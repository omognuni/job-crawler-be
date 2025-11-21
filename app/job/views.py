"""
Job Posting Views

채용 공고 API 엔드포인트 (Thin Controller)
"""

import logging

from job.models import JobPosting
from job.serializers import JobPostingSerializer
from job.services import JobService
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

logger = logging.getLogger(__name__)


class JobPostingViewSet(ModelViewSet):
    """
    채용 공고 ViewSet (Thin Controller)

    비즈니스 로직은 JobService에 위임하고,
    HTTP 요청/응답 처리만 담당합니다.
    """

    queryset = JobPosting.objects.all()
    serializer_class = JobPostingSerializer

    def list(self, request, *args, **kwargs):
        """
        채용 공고 목록 조회

        GET /api/v1/jobs/
        """
        try:
            job_postings = JobService.get_all_job_postings()
            serializer = self.get_serializer(job_postings, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Failed to list job postings: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve job postings"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, pk=None, *args, **kwargs):
        """
        채용 공고 상세 조회

        GET /api/v1/jobs/<posting_id>/
        """
        try:
            job_posting = JobService.get_job_posting(int(pk))
            if not job_posting:
                return Response(
                    {"error": "Job posting not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = self.get_serializer(job_posting)
            return Response(serializer.data)
        except Exception as e:
            logger.error(
                f"Failed to retrieve job posting {pk}: {str(e)}", exc_info=True
            )
            return Response(
                {"error": "Failed to retrieve job posting"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def create(self, request, *args, **kwargs):
        """
        채용 공고 생성

        POST /api/v1/jobs/
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Service를 통해 생성 (save() 메서드가 자동으로 Celery 작업 호출)
            job_posting = JobService.create_job_posting(serializer.validated_data)

            response_serializer = self.get_serializer(job_posting)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Failed to create job posting: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to create job posting"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update(self, request, pk=None, *args, **kwargs):
        """
        채용 공고 수정 (전체)

        PUT /api/v1/jobs/<posting_id>/
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            job_posting = JobService.update_job_posting(
                int(pk), serializer.validated_data
            )
            if not job_posting:
                return Response(
                    {"error": "Job posting not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            response_serializer = self.get_serializer(job_posting)
            return Response(response_serializer.data)
        except Exception as e:
            logger.error(f"Failed to update job posting {pk}: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to update job posting"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def partial_update(self, request, pk=None, *args, **kwargs):
        """
        채용 공고 수정 (부분)

        PATCH /api/v1/jobs/<posting_id>/
        """
        try:
            serializer = self.get_serializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            job_posting = JobService.update_job_posting(
                int(pk), serializer.validated_data
            )
            if not job_posting:
                return Response(
                    {"error": "Job posting not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            response_serializer = self.get_serializer(job_posting)
            return Response(response_serializer.data)
        except Exception as e:
            logger.error(
                f"Failed to partially update job posting {pk}: {str(e)}",
                exc_info=True,
            )
            return Response(
                {"error": "Failed to update job posting"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, pk=None, *args, **kwargs):
        """
        채용 공고 삭제

        DELETE /api/v1/jobs/<posting_id>/
        """
        try:
            success = JobService.delete_job_posting(int(pk))
            if not success:
                return Response(
                    {"error": "Job posting not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Failed to delete job posting {pk}: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to delete job posting"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# class ResumeViewSet(ModelViewSet):
#     queryset = Resume.objects.all()
#     serializer_class = ResumeSerializer


# class JobRecommendationViewSet(ModelViewSet):
#     """
#     채용 공고 추천 ViewSet

#     AI-Free 실시간 추천 엔진을 사용하여 사용자에게 맞춤형 채용 공고를 추천합니다.
#     """

#     queryset = JobRecommendation.objects.all()
#     serializer_class = JobRecommendationSerializer
#     permission_classes = [AllowAny]

#     @action(detail=False, methods=["get"], url_path="for-user/(?P<user_id>[0-9]+)")
#     def for_user(self, request, user_id=None):
#         """
#         특정 사용자를 위한 실시간 추천 생성

#         GET /api/job/recommendations/for-user/<user_id>/?limit=10

#         Args:
#             user_id: 사용자 ID (URL 파라미터)
#             limit: 반환할 추천 개수 (쿼리 파라미터, 기본값 10)

#         Returns:
#             실시간 생성된 추천 공고 리스트
#         """
#         start_time = time.time()

#         try:
#             user_id = int(user_id)
#             limit = int(request.query_params.get("limit", 10))
#         except ValueError:
#             return Response(
#                 {"error": "user_id and limit must be integers"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         # 실시간 추천 생성
#         recommendations = get_recommendations(user_id, limit=limit)

#         # 응답 시간 로깅
#         elapsed_time = time.time() - start_time
#         logger.info(
#             f"Generated {len(recommendations)} recommendations for user {user_id} "
#             f"in {elapsed_time:.3f} seconds"
#         )

#         return Response(
#             {
#                 "user_id": user_id,
#                 "count": len(recommendations),
#                 "recommendations": recommendations,
#                 "response_time_seconds": round(elapsed_time, 3),
#             }
#         )

#     def list(self, request, *args, **kwargs):
#         """
#         사용자별 저장된 추천 목록 조회

#         GET /api/job/recommendations/?user_id=<int>
#         """
#         user_id = request.query_params.get("user_id")

#         if user_id:
#             try:
#                 user_id = int(user_id)
#                 self.queryset = self.queryset.filter(user_id=user_id)
#             except ValueError:
#                 return Response(
#                     {"error": "user_id must be an integer"},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )

#         return super().list(request, *args, **kwargs)


# # JobSearchView: search.views.JobSearchView로 이동 (Phase 2.2)
# # RelatedJobsView: skill.views.RelatedJobsView로 이동 (Phase 2.1)


# class RecommendationsView(APIView):
#     """
#     AI-Free 실시간 채용 공고 추천 API
#     """

#     permission_classes = [AllowAny]

#     def get(self, request):
#         """
#         GET /api/job/recommendations?user_id=<int>&limit=<int>

#         Args:
#             user_id: 사용자 ID (필수)
#             limit: 반환할 추천 개수 (선택, 기본값 10)

#         Returns:
#             추천 공고 리스트
#         """
#         from job.recommender import get_recommendations

#         user_id = request.query_params.get("user_id")
#         limit = request.query_params.get("limit", 10)

#         # 파라미터 검증
#         if not user_id:
#             return Response({"error": "user_id parameter is required"}, status=400)

#         try:
#             user_id = int(user_id)
#             limit = int(limit)
#         except ValueError:
#             return Response({"error": "user_id and limit must be integers"}, status=400)

#         # 추천 생성
#         recommendations = get_recommendations(user_id, limit=limit)

#         return Response(
#             {
#                 "user_id": user_id,
#                 "count": len(recommendations),
#                 "recommendations": recommendations,
#             }
#         )

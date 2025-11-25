"""
Job Posting Views

채용 공고 API 엔드포인트 (Thin Controller)
"""

import logging

from job.models import JobPosting
from job.permissions import HasSimpleSecretKey
from job.serializers import JobPostingSerializer
from job.services import JobService
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

logger = logging.getLogger(__name__)


class JobPostingViewSet(GenericViewSet):
    """
    채용 공고 ViewSet (Thin Controller)

    비즈니스 로직은 JobService에 위임하고,
    HTTP 요청/응답 처리만 담당합니다.
    """

    queryset = JobPosting.objects.all()
    serializer_class = JobPostingSerializer
    permission_classes = [HasSimpleSecretKey | IsAuthenticated]

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

"""
Resume Views

이력서 API 엔드포인트 (Thin Controller)
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from resume.models import Resume
from resume.serializers import ResumeSerializer
from resume.services import ResumeService

logger = logging.getLogger(__name__)


class ResumeViewSet(ModelViewSet):
    """
    이력서 ViewSet (Thin Controller)

    비즈니스 로직은 ResumeService에 위임하고,
    HTTP 요청/응답 처리만 담당합니다.
    """

    queryset = Resume.objects.all()
    serializer_class = ResumeSerializer
    lookup_field = "user_id"

    def list(self, request, *args, **kwargs):
        """
        이력서 목록 조회

        GET /api/v1/resumes/
        """
        try:
            resumes = ResumeService.get_all_resumes()
            serializer = self.get_serializer(resumes, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Failed to list resumes: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve resumes"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, user_id=None, *args, **kwargs):
        """
        이력서 상세 조회

        GET /api/v1/resumes/<user_id>/
        """
        try:
            resume = ResumeService.get_resume(int(user_id))
            if not resume:
                return Response(
                    {"error": "Resume not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = self.get_serializer(resume)
            return Response(serializer.data)
        except Exception as e:
            logger.error(
                f"Failed to retrieve resume {user_id}: {str(e)}", exc_info=True
            )
            return Response(
                {"error": "Failed to retrieve resume"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def create(self, request, *args, **kwargs):
        """
        이력서 생성

        POST /api/v1/resumes/
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Service를 통해 생성 (save() 메서드가 자동으로 Celery 작업 호출)
            resume = ResumeService.create_resume(serializer.validated_data)

            response_serializer = self.get_serializer(resume)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Failed to create resume: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to create resume"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update(self, request, user_id=None, *args, **kwargs):
        """
        이력서 수정 (전체)

        PUT /api/v1/resumes/<user_id>/
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            resume = ResumeService.update_resume(
                int(user_id), serializer.validated_data
            )
            if not resume:
                return Response(
                    {"error": "Resume not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            response_serializer = self.get_serializer(resume)
            return Response(response_serializer.data)
        except Exception as e:
            logger.error(f"Failed to update resume {user_id}: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to update resume"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def partial_update(self, request, user_id=None, *args, **kwargs):
        """
        이력서 수정 (부분)

        PATCH /api/v1/resumes/<user_id>/
        """
        try:
            serializer = self.get_serializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            resume = ResumeService.update_resume(
                int(user_id), serializer.validated_data
            )
            if not resume:
                return Response(
                    {"error": "Resume not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            response_serializer = self.get_serializer(resume)
            return Response(response_serializer.data)
        except Exception as e:
            logger.error(
                f"Failed to partially update resume {user_id}: {str(e)}",
                exc_info=True,
            )
            return Response(
                {"error": "Failed to update resume"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, user_id=None, *args, **kwargs):
        """
        이력서 삭제

        DELETE /api/v1/resumes/<user_id>/
        """
        try:
            success = ResumeService.delete_resume(int(user_id))
            if not success:
                return Response(
                    {"error": "Resume not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Failed to delete resume {user_id}: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to delete resume"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

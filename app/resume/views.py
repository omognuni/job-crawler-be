"""
Resume Views

이력서 API 엔드포인트 (Thin Controller)
"""

import logging

from celery.result import AsyncResult
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from resume.models import Resume
from resume.serializers import ResumeSerializer
from resume.services import ResumeService
from resume.tasks import process_resume

logger = logging.getLogger(__name__)


from rest_framework.permissions import IsAuthenticated


class ResumeViewSet(ModelViewSet):
    """
    이력서 ViewSet (Thin Controller)

    비즈니스 로직은 ResumeService에 위임하고,
    HTTP 요청/응답 처리만 담당합니다.
    """

    queryset = Resume.objects.all()
    serializer_class = ResumeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        요청을 보낸 사용자의 이력서만 조회
        """
        return Resume.objects.filter(user_id=self.request.user.id)

    def list(self, request, *args, **kwargs):
        """
        이력서 목록 조회

        GET /api/v1/resumes/
        """
        # get_queryset()을 통해 현재 사용자의 이력서만 반환
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        이력서 상세 조회

        GET /api/v1/resumes/<resume_id>/
        """
        # get_queryset() 범위 내에서 pk로 조회
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        이력서 생성

        POST /api/v1/resumes/
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # user_id 주입
            validated_data = serializer.validated_data
            validated_data["user_id"] = request.user.id

            # Service를 통해 생성 (save() 메서드가 자동으로 Celery 작업 호출)
            resume = ResumeService.create_resume(validated_data)

            response_serializer = self.get_serializer(resume)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Failed to create resume: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to create resume"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update(self, request, pk=None, *args, **kwargs):
        """
        이력서 수정 (전체)

        PUT /api/v1/resumes/<resume_id>/
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data)
            serializer.is_valid(raise_exception=True)

            resume = ResumeService.update_resume(
                int(pk), request.user.id, serializer.validated_data
            )
            if not resume:
                return Response(
                    {"error": "Resume not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            response_serializer = self.get_serializer(resume)
            return Response(response_serializer.data)
        except Exception as e:
            logger.error(f"Failed to update resume {pk}: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to update resume"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def partial_update(self, request, pk=None, *args, **kwargs):
        """
        이력서 수정 (부분)

        PATCH /api/v1/resumes/<resume_id>/
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            resume = ResumeService.update_resume(
                int(pk), request.user.id, serializer.validated_data
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
                f"Failed to partially update resume {pk}: {str(e)}",
                exc_info=True,
            )
            return Response(
                {"error": "Failed to update resume"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, pk=None, *args, **kwargs):
        """
        이력서 삭제

        DELETE /api/v1/resumes/<resume_id>/
        """
        try:
            success = ResumeService.delete_resume(int(pk), request.user.id)
            if not success:
                return Response(
                    {"error": "Resume not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Failed to delete resume {pk}: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to delete resume"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(methods=["GET"], detail=True, url_path="analyze", url_name="analyze")
    def analyze(self, request, pk=None, *args, **kwargs):
        """
        이력서 분석

        GET /api/v1/resumes/<resume_id>/analyze/
        """
        try:
            resume = self.get_object()
            async_result = process_resume.delay(int(resume.id))
            # 상태 조회를 위해 task_id 저장
            Resume.objects.filter(pk=resume.id).update(
                last_process_task_id=async_result.id,
            )
            return Response(
                {"task_id": async_result.id},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as e:
            logger.error(f"Failed to analyze resume {pk}: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to analyze resume"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        methods=["GET"],
        detail=True,
        url_path="analyze-status",
        url_name="analyze-status",
    )
    def analyze_status(self, request, pk=None, *args, **kwargs):
        """
        이력서 분석 상태 조회

        GET /api/v1/resumes/<resume_id>/analyze-status/
        """
        resume = self.get_object()
        task_id = resume.last_process_task_id
        if not task_id:
            return Response(
                {"state": "not_started", "task_id": None},
                status=status.HTTP_200_OK,
            )

        async_result = AsyncResult(task_id)
        state = async_result.state

        if state in {"PENDING", "RECEIVED", "STARTED", "RETRY"}:
            return Response(
                {"state": "processing", "task_id": task_id, "celery_state": state},
                status=status.HTTP_200_OK,
            )

        if state == "SUCCESS":
            # 최신 Resume 정보를 함께 반환
            resume.refresh_from_db()
            serializer = self.get_serializer(resume)
            return Response(
                {"state": "success", "task_id": task_id, "resume": serializer.data},
                status=status.HTTP_200_OK,
            )

        # FAILURE 및 기타
        error = None
        try:
            error = str(async_result.result) if async_result.result else None
        except Exception:
            error = None
        return Response(
            {
                "state": "failure",
                "task_id": task_id,
                "celery_state": state,
                "error": error,
            },
            status=status.HTTP_200_OK,
        )

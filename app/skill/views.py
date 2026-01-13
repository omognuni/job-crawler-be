"""
Skill Views

스킬 관련 API 뷰
"""

from common.graph_db import graph_db_client
from drf_spectacular.utils import extend_schema
from job.models import JobPosting
from job.serializers import JobPostingSerializer
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from skill.services import SkillExtractionService


class SkillOptionsView(APIView):
    """
    기술스택 옵션 목록 조회 (public)

    FE 필터 UI에서 미리 옵션을 로드해 사용할 수 있도록,
    지원하는 전체 스킬 목록(마스터 목록)을 반환합니다.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get Skill Options",
        description="Return all supported skills as a sorted string array.",
        responses={200: list[str]},
    )
    def get(self, request):
        return Response(SkillExtractionService.get_all_skills(), status=200)


class RelatedJobsBySkillView(APIView):
    """
    특정 스킬과 관련된 채용 공고 조회

    Neo4j 그래프 DB를 사용하여 스킬 기반 공고 검색을 수행합니다.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        responses=JobPostingSerializer(many=True),
        summary="Get Related Jobs by Skill",
        description="Get job postings related to a specific skill using Graph DB.",
    )
    def get(self, request, skill_name: str):
        # Neo4j에서 스킬 관련 공고 ID 조회
        posting_ids = graph_db_client.get_jobs_related_to_skill(skill_name)

        if not posting_ids:
            return Response([], status=200)

        # PostgreSQL에서 공고 상세 정보 조회
        job_postings = JobPosting.objects.filter(posting_id__in=posting_ids)
        serializer = JobPostingSerializer(job_postings, many=True)

        return Response(serializer.data)

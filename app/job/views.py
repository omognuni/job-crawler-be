import json

from agent.tools import vector_search_job_postings_tool
from common.graph_db import graph_db_client
from job.models import JobPosting, JobRecommendation, Resume
from job.serializers import (
    JobPostingSerializer,
    JobRecommendationSerializer,
    ResumeSerializer,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet


class JobPostingViewSet(ModelViewSet):
    queryset = JobPosting.objects.all()
    serializer_class = JobPostingSerializer


class ResumeViewSet(ModelViewSet):
    queryset = Resume.objects.all()
    serializer_class = ResumeSerializer


class JobRecommendationViewSet(ModelViewSet):
    queryset = JobRecommendation.objects.all()
    serializer_class = JobRecommendationSerializer


class JobSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get("query")
        if not query:
            return Response({"error": "Query parameter is required"}, status=400)

        result_json = vector_search_job_postings_tool.run(query_text=query)
        return Response(json.loads(result_json))


class RelatedJobsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, skill_name: str):
        posting_ids = graph_db_client.get_jobs_related_to_skill(skill_name)

        if not posting_ids:
            return Response([], status=200)

        job_postings = JobPosting.objects.filter(posting_id__in=posting_ids)
        serializer = JobPostingSerializer(job_postings, many=True)
        return Response(serializer.data)

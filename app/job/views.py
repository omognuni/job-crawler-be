from job.models import JobPosting, JobRecommendation, Resume
from job.serializers import (
    JobPostingSerializer,
    JobRecommendationSerializer,
    ResumeSerializer,
)
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

from rest_framework.viewsets import GenericViewSet, ModelViewSet
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from app.agent.models import JobPosting, Resume, JobRecommendation
from app.agent.serializers import JobPostingSerializer, ResumeSerializer, JobRecommendationSerializer
# Create your views here.
class JobPostingViewSet(ModelViewSet):
    queryset = JobPosting.objects.all()
    serializer_class = JobPostingSerializer
    
class ResumeViewSet(ModelViewSet):
    queryset = Resume.objects.all()
    serializer_class = ResumeSerializer
    
class JobRecommendationViewSet(ModelViewSet):
    queryset = JobRecommendation.objects.all()
    serializer_class = JobRecommendationSerializer
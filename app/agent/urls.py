from django.urls import path, include
from rest_framework.routers import DefaultRouter
from agent.views import JobPostingViewSet, ResumeViewSet, JobRecommendationViewSet

router = DefaultRouter()
router.register(r'job-postings', JobPostingViewSet, basename='jobposting')
router.register(r'resumes', ResumeViewSet, basename='resume')
router.register(r'recommendations', JobRecommendationViewSet, basename='recommendation')

urlpatterns = [
    path('', include(router.urls)),
]


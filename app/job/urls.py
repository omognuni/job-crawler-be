from django.urls import include, path
from job.views import JobPostingViewSet, JobRecommendationViewSet, ResumeViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"job-postings", JobPostingViewSet, basename="jobposting")
router.register(r"resumes", ResumeViewSet, basename="resume")
router.register(r"recommendations", JobRecommendationViewSet, basename="recommendation")

urlpatterns = [
    path("", include(router.urls)),
]

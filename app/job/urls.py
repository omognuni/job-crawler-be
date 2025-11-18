from django.urls import include, path
from job.views import (
    JobPostingViewSet,
    JobRecommendationViewSet,
    JobSearchView,
    RecommendationsView,
    RelatedJobsView,
    ResumeViewSet,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"job-postings", JobPostingViewSet, basename="jobposting")
router.register(r"resumes", ResumeViewSet, basename="resume")
router.register(r"recommendations", JobRecommendationViewSet, basename="recommendation")

urlpatterns = [
    path("", include(router.urls)),
    path("search/", JobSearchView.as_view(), name="job-search"),
    path(
        "related-by-skill/<str:skill_name>/",
        RelatedJobsView.as_view(),
        name="related-jobs-by-skill",
    ),
    path(
        "recommend/",
        RecommendationsView.as_view(),
        name="realtime-recommendations",
    ),
]

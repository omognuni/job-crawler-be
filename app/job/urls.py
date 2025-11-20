from django.urls import include, path

# from job.views import (
#     JobPostingViewSet,
#     JobRecommendationViewSet,
#     RecommendationsView,
#     ResumeViewSet,
# )
# from rest_framework.routers import DefaultRouter

# router = DefaultRouter()
# router.register(r"job-postings", JobPostingViewSet, basename="jobposting")
# router.register(r"resumes", ResumeViewSet, basename="resume")
# router.register(r"recommendations", JobRecommendationViewSet, basename="recommendation")

urlpatterns = [
    #     path("", include(router.urls)),
    #     # JobSearchView: search.urls로 이동 (Phase 2.2)
    #     # RelatedJobsView: skill.urls로 이동 (Phase 2.1)
    #     path(
    #         "recommend/",
    #         RecommendationsView.as_view(),
    #         name="realtime-recommendations",
    #     ),
]

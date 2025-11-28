from django.urls import include, path
from recommendation.views import JobRecommendationViewSet, RecommendationPromptViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(
    r"prompts", RecommendationPromptViewSet, basename="recommendation-prompt"
)
router.register(r"", JobRecommendationViewSet, basename="recommendation")

urlpatterns = [
    path("", include(router.urls)),
]

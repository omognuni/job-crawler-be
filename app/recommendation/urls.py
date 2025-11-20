from django.urls import include, path
from recommendation.views import JobRecommendationViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"", JobRecommendationViewSet, basename="recommendation")

urlpatterns = [
    path("", include(router.urls)),
]

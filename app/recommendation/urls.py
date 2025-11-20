from django.urls import include, path
from rest_framework.routers import DefaultRouter

# TODO: ViewSet 이동 후 라우터 설정
# router = DefaultRouter()
# router.register(r"", JobRecommendationViewSet, basename="recommendation")

urlpatterns = [
    # path("", include(router.urls)),
    # path("for-user/<int:user_id>/", ..., name="recommendations-for-user"),
]

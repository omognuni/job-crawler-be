from django.urls import include, path
from job.views import JobPostingViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"", JobPostingViewSet, basename="job")

urlpatterns = [
    path("", include(router.urls)),
]

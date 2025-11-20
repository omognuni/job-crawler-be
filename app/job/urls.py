from django.urls import include, path
from job.views import JobPostingViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"job-postings", JobPostingViewSet, basename="jobposting")

urlpatterns = [
    path("", include(router.urls)),
]

from django.urls import include, path
from job.views import CompanyOptionsView, JobPostingViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"", JobPostingViewSet, basename="job")

urlpatterns = [
    # NOTE: router 보다 먼저 두어야 /companies/ 가 pk 로 오인되지 않습니다.
    path("companies/", CompanyOptionsView.as_view(), name="job-company-options"),
    path("", include(router.urls)),
]

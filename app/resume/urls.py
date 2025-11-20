from django.urls import include, path
from rest_framework.routers import DefaultRouter
from resume.views import ResumeViewSet

router = DefaultRouter()
router.register(r"", ResumeViewSet, basename="resume")

urlpatterns = [
    path("", include(router.urls)),
]

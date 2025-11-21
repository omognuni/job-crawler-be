from django.urls import path

from .views import HybridSearchView, JobSearchView

urlpatterns = [
    path("", JobSearchView.as_view(), name="job-search"),
    path("hybrid/", HybridSearchView.as_view(), name="hybrid-search"),
]

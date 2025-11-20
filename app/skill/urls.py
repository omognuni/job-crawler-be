from django.urls import path

from .views import RelatedJobsBySkillView

urlpatterns = [
    path(
        "related/<str:skill_name>/",
        RelatedJobsBySkillView.as_view(),
        name="related-jobs-by-skill",
    ),
]

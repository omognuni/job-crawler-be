from django.urls import path

from .views import RelatedJobsBySkillView, SkillOptionsView

urlpatterns = [
    path(
        "",
        SkillOptionsView.as_view(),
        name="skill-options",
    ),
    path(
        "related/<str:skill_name>/",
        RelatedJobsBySkillView.as_view(),
        name="related-jobs-by-skill",
    ),
]

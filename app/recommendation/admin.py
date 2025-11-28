from django.contrib import admin
from recommendation.models import JobRecommendation, RecommendationPrompt


@admin.register(JobRecommendation)
class JobRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "user_id",
        "rank",
        "job_posting",
        "match_score",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("user_id", "job_posting__company_name")


@admin.register(RecommendationPrompt)
class RecommendationPromptAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "content")

from django.contrib import admin
from recommendation.models import JobRecommendation


@admin.register(JobRecommendation)
class JobRecommendationAdmin(admin.ModelAdmin):
    list_display = ["user_id", "job_posting", "rank", "created_at"]
    search_fields = ["user_id", "job_posting__company_name", "job_posting__position"]

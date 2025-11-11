from django.contrib import admin
from job.models import JobPosting, JobRecommendation, Resume


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ["posting_id", "company_name", "position", "created_at"]
    search_fields = ["company_name", "position"]
    list_filter = ["created_at"]
    ordering = ["-created_at"]
    list_per_page = 100


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = [
        "user_id",
        "created_at",
    ]
    search_fields = ["user_id"]
    list_filter = ["created_at"]
    ordering = ["-created_at"]
    list_per_page = 100


@admin.register(JobRecommendation)
class JobRecommendationAdmin(admin.ModelAdmin):
    list_display = ["user_id", "job_posting", "rank", "created_at"]
    search_fields = ["user_id", "job_posting__company_name", "job_posting__position"]

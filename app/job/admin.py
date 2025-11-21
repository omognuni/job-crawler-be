from django.contrib import admin
from job.models import JobPosting


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ["posting_id", "company_name", "position", "created_at"]
    search_fields = ["company_name", "position"]
    list_filter = ["created_at"]
    ordering = ["-created_at"]
    list_per_page = 100

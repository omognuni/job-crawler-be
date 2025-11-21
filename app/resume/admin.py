from django.contrib import admin
from resume.models import Resume


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

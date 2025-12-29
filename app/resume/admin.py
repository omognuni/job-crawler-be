from django.contrib import admin, messages
from resume.models import Resume
from resume.tasks import process_resume


@admin.action(description="선택 이력서 재임베딩(LLM 분석 생략) 실행")
def action_reembed_resumes(modeladmin, request, queryset):
    queued = 0
    for resume in queryset.iterator():
        process_resume.delay(resume.id, force_reindex=True)
        queued += 1

    modeladmin.message_user(
        request,
        f"{queued}개 이력서 재임베딩 작업을 큐에 등록했습니다.",
        level=messages.SUCCESS,
    )


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
    actions = [action_reembed_resumes]

from django.contrib import admin, messages
from job.models import JobPosting
from job.tasks import process_job_posting


@admin.action(description="선택 공고 재임베딩 실행")
def action_reembed_job_postings(modeladmin, request, queryset):
    queued = 0
    for posting in queryset.iterator():
        process_job_posting.delay(posting.posting_id, reindex=True)
        queued += 1

    modeladmin.message_user(
        request,
        f"{queued}개 채용 공고 재임베딩 작업을 큐에 등록했습니다.",
        level=messages.SUCCESS,
    )


@admin.action(description="전체 공고 재임베딩 실행(주의: 전체 큐 등록)")
def action_reembed_all_job_postings(modeladmin, request, queryset):
    # 실수 방지: superuser만 실행 가능
    if not request.user.is_superuser:
        modeladmin.message_user(
            request,
            "권한이 없습니다. (superuser만 전체 재임베딩 실행 가능)",
            level=messages.ERROR,
        )
        return

    queued = 0
    for posting_id in JobPosting.objects.values_list(
        "posting_id", flat=True
    ).iterator():
        process_job_posting.delay(int(posting_id), reindex=True)
        queued += 1

    modeladmin.message_user(
        request,
        f"전체 {queued}개 채용 공고 재임베딩 작업을 큐에 등록했습니다.",
        level=messages.SUCCESS,
    )


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ["posting_id", "company_name", "position", "created_at"]
    search_fields = ["company_name", "position"]
    list_filter = ["created_at"]
    ordering = ["-created_at"]
    list_per_page = 100
    actions = [action_reembed_job_postings, action_reembed_all_job_postings]

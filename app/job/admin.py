from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.http import HttpResponseRedirect
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

    def changelist_view(self, request, extra_context=None):
        """
        Django Admin 액션은 기본적으로 체크박스 선택이 없으면 액션을 실행하지 않고 경고를 띄웁니다.
        '전체 공고 재임베딩' 액션만은 선택 없이도 실행되도록 changelist_view에서 선처리합니다.
        """
        if request.method == "POST":
            action = request.POST.get("action") or request.POST.get("action2")
            selected = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
            if action == "action_reembed_all_job_postings" and not selected:
                # 선택이 없으면 전체 대상으로 실행
                action_reembed_all_job_postings(self, request, JobPosting.objects.all())
                return HttpResponseRedirect(request.get_full_path())

        return super().changelist_view(request, extra_context=extra_context)

    def response_action(self, request, queryset):
        """
        Django Admin 기본 동작은 액션 실행 시 최소 1개 이상 선택을 요구합니다.
        '전체 공고 재임베딩' 액션에 한해, 선택이 없더라도 전체 queryset으로 실행되도록 예외 처리합니다.
        """
        # 상단 액션은 action, 하단 액션은 action2로 들어올 수 있음
        action = request.POST.get("action") or request.POST.get("action2")
        if action == "action_reembed_all_job_postings":
            selected = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
            if not selected:
                action_func = self.get_actions(request)[action][0]
                action_func(self, request, JobPosting.objects.all())
                return HttpResponseRedirect(request.get_full_path())

        return super().response_action(request, queryset)

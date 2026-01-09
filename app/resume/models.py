import hashlib

from django.conf import settings
from django.db import models, transaction


class Resume(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resumes",
    )
    title = models.CharField(
        max_length=100, default="내 이력서", help_text="이력서 제목"
    )
    is_primary = models.BooleanField(
        default=False, help_text="대표 이력서 여부 (추천 대상)"
    )
    content = models.TextField(help_text="이력서 원본 내용")
    content_hash = models.CharField(
        max_length=64, help_text="이력서 내용 해시값", blank=True, null=True
    )
    analysis_result = models.JSONField(
        null=True, blank=True, help_text="이력서 분석 결과 (캐시)"
    )
    experience_summary = models.TextField(
        null=True, blank=True, help_text="경력 요약 (임베딩용)"
    )
    analyzed_at = models.DateTimeField(
        null=True, blank=True, help_text="마지막 분석 시간"
    )
    analyzed_content_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="마지막 분석 시점의 content_hash (변경 감지용)",
    )
    last_process_task_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="마지막 이력서 처리(Celery) task_id",
    )
    last_process_task_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="마지막 이력서 처리(Celery) task_id 갱신 시간",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agent_resume"

    def __str__(self):
        return f"Resume {self.id} ({self.title}) for user {self.user_id}"

    def calculate_hash(self) -> str:
        """이력서 내용의 해시값 계산"""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        """
        저장 시 해시값 자동 갱신
        """
        # update_fields에 "분석/처리 결과"만 포함된 경우, 자동 처리 태스크 스케줄링을 스킵합니다.
        # (무한 루프 방지 - 처리 태스크가 analysis_result 등을 업데이트하기 때문)
        update_fields = kwargs.get("update_fields")
        analysis_update_fields = {
            "analysis_result",
            "experience_summary",
            "analyzed_at",
            "analyzed_content_hash",
            "last_process_task_id",
            "last_process_task_updated_at",
        }
        auto_enabled = getattr(settings, "AUTO_PROCESS_RESUME_ON_SAVE", True)
        should_schedule_processing = auto_enabled and (
            update_fields is None
            or not set(update_fields).issubset(analysis_update_fields)
        )

        old_content_hash = None
        if self.pk and should_schedule_processing:
            old_content_hash = (
                Resume.objects.filter(pk=self.pk)
                .values_list("content_hash", flat=True)
                .first()
            )

        # 대표 이력서 설정 시 다른 이력서 해제
        if self.is_primary:
            Resume.objects.filter(user=self.user, is_primary=True).exclude(
                id=self.id
            ).update(is_primary=False)

        self.content_hash = self.calculate_hash()

        super().save(*args, **kwargs)

        # 트랜잭션 커밋 후 비동기 처리 태스크 스케줄링
        if should_schedule_processing and (
            old_content_hash is None or old_content_hash != self.content_hash
        ):
            transaction.on_commit(lambda: self._schedule_processing())

    def _schedule_processing(self):
        """비동기 처리 태스크 스케줄링"""
        from django.utils import timezone

        from .tasks import process_resume

        async_result = process_resume.delay(self.id)
        Resume.objects.filter(pk=self.pk).update(
            last_process_task_id=async_result.id,
            last_process_task_updated_at=timezone.now(),
        )

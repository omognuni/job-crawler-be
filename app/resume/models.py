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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agent_resume"

    def __str__(self):
        return f"Resume {self.id} ({self.title}) for user {self.user_id}"

    def calculate_hash(self) -> str:
        """이력서 내용의 해시값 계산"""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def needs_analysis(self) -> bool:
        """이력서 분석이 필요한지 확인"""
        current_hash = self.calculate_hash()
        return (
            self.content_hash != current_hash
            or self.analysis_result is None
            or self.analyzed_at is None
        )

    def save(self, *args, **kwargs):
        """
        저장 시 해시값 자동 갱신 및 비동기 처리 태스크 호출
        """
        # 대표 이력서 설정 시 다른 이력서 해제
        if self.is_primary:
            Resume.objects.filter(user=self.user, is_primary=True).exclude(
                id=self.id
            ).update(is_primary=False)

        # 해시값 계산
        old_hash = self.content_hash
        self.content_hash = self.calculate_hash()

        # update_fields에 분석 결과 필드만 포함된 경우 태스크 호출 스킵
        # (무한 루프 방지)
        update_fields = kwargs.get("update_fields")
        should_process = update_fields is None or not set(update_fields).issubset(
            {"analysis_result", "experience_summary", "analyzed_at", "content_hash"}
        )

        # 모델 저장
        super().save(*args, **kwargs)

        # 트랜잭션 커밋 후 비동기 처리 (내용이 변경된 경우에만)
        if should_process and old_hash != self.content_hash:
            transaction.on_commit(lambda: self._schedule_processing())

    def _schedule_processing(self):
        """비동기 처리 태스크 스케줄링"""
        from .tasks import process_resume

        process_resume.delay(self.id)

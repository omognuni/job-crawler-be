from django.db import models, transaction


class JobPosting(models.Model):
    posting_id = models.IntegerField(primary_key=True)
    url = models.URLField(max_length=255)
    company_name = models.CharField(max_length=255)
    position = models.CharField(max_length=255)
    main_tasks = models.TextField()
    requirements = models.TextField()
    preferred_points = models.TextField()
    location = models.CharField(max_length=255)
    district = models.CharField(max_length=255)
    employment_type = models.CharField(max_length=255)
    career_min = models.IntegerField()
    career_max = models.IntegerField()
    skills_required = models.JSONField(
        null=True, blank=True, help_text="요구 기술 스택 (JSON 배열)"
    )
    skills_preferred = models.TextField(
        null=True, blank=True, help_text="우대 사항 원문"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agent_job_posting"

    def __str__(self):
        return f"{self.company_name} - {self.position} - {self.url}"

    def save(self, *args, **kwargs):
        """
        저장 후 트랜잭션 커밋 시 비동기 처리 태스크 호출
        """
        # update_fields에 skills_* 필드가 포함된 경우 태스크 호출 스킵
        # (무한 루프 방지 - tasks.py에서 이미 스킬 업데이트 수행)
        update_fields = kwargs.get("update_fields")
        should_process = update_fields is None or not set(update_fields).issubset(
            {"skills_required", "skills_preferred"}
        )

        # 모델 저장
        super().save(*args, **kwargs)

        # 트랜잭션 커밋 후 비동기 처리
        if should_process:
            transaction.on_commit(lambda: self._schedule_processing())

    def _schedule_processing(self):
        """비동기 처리 태스크 스케줄링"""
        from .tasks import process_job_posting

        process_job_posting.delay(self.posting_id)

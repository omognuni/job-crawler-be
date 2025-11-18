import hashlib

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


class Resume(models.Model):
    user_id = models.IntegerField(unique=True)
    content = models.TextField(help_text="이력서 원본 내용")
    content_hash = models.CharField(max_length=64, help_text="이력서 내용 해시값")
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
        return f"Resume for user {self.user_id}"

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

        process_resume.delay(self.user_id)


class JobRecommendation(models.Model):
    user_id = models.IntegerField()
    job_posting = models.ForeignKey("JobPosting", on_delete=models.CASCADE)
    rank = models.IntegerField(help_text="추천 순위 (1-10)")
    match_score = models.FloatField(help_text="매칭 점수")
    match_reason = models.TextField(help_text="추천 이유")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_job_recommendation"
        ordering = ["user_id", "rank"]
        unique_together = ["user_id", "rank", "created_at"]

    def __str__(self):
        return (
            f"Recommendation #{self.rank} for user {self.user_id}: {self.job_posting}"
        )

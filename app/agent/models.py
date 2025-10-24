from django.db import models
import hashlib
import json


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_name} - {self.position} - {self.url}"


class Resume(models.Model):
    user_id = models.IntegerField(unique=True)
    content = models.TextField(help_text="이력서 원본 내용")
    content_hash = models.CharField(max_length=64, help_text="이력서 내용 해시값")
    analysis_result = models.JSONField(null=True, blank=True, help_text="이력서 분석 결과 (캐시)")
    analyzed_at = models.DateTimeField(null=True, blank=True, help_text="마지막 분석 시간")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Resume for user {self.user_id}"

    def calculate_hash(self) -> str:
        """이력서 내용의 해시값 계산"""
        return hashlib.sha256(self.content.encode('utf-8')).hexdigest()

    def needs_analysis(self) -> bool:
        """이력서 분석이 필요한지 확인"""
        current_hash = self.calculate_hash()
        return (
            self.content_hash != current_hash or 
            self.analysis_result is None or 
            self.analyzed_at is None
        )

    def save(self, *args, **kwargs):
        """저장 시 해시값 자동 갱신"""
        self.content_hash = self.calculate_hash()
        super().save(*args, **kwargs)


class JobRecommendation(models.Model):
    user_id = models.IntegerField()
    job_posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE)
    rank = models.IntegerField(help_text="추천 순위 (1-10)")
    match_score = models.FloatField(help_text="매칭 점수")
    match_reason = models.TextField(help_text="추천 이유")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['user_id', 'rank']
        unique_together = ['user_id', 'rank', 'created_at']

    def __str__(self):
        return f"Recommendation #{self.rank} for user {self.user_id}: {self.job_posting}"
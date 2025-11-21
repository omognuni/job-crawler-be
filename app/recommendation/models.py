from django.db import models


class JobRecommendation(models.Model):
    user_id = models.IntegerField()
    job_posting = models.ForeignKey("job.JobPosting", on_delete=models.CASCADE)
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

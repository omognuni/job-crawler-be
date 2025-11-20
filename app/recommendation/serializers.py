from job.serializers import JobPostingSerializer
from recommendation.models import JobRecommendation
from rest_framework import serializers


class JobRecommendationSerializer(serializers.ModelSerializer):
    job_posting = JobPostingSerializer(read_only=True)

    class Meta:
        model = JobRecommendation
        fields = [
            "id",
            "user_id",
            "job_posting",
            "rank",
            "match_score",
            "match_reason",
            "created_at",
        ]

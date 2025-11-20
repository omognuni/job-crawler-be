from job.models import JobPosting
from job.serializers import JobPostingSerializer
from recommendation.models import JobRecommendation
from rest_framework import serializers


class JobRecommendationReadSerializer(serializers.ModelSerializer):
    """GET 요청용 Serializer - job_posting 전체 정보 포함"""

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
        read_only_fields = ["id", "created_at"]


class JobRecommendationWriteSerializer(serializers.ModelSerializer):
    """POST/PUT/PATCH 요청용 Serializer - job_posting ID만 받음"""

    job_posting = serializers.PrimaryKeyRelatedField(
        queryset=JobPosting.objects.all(), pk_field=serializers.IntegerField()
    )

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
        read_only_fields = ["id", "created_at"]

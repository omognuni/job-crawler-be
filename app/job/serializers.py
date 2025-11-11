from job.models import JobPosting, JobRecommendation, Resume
from rest_framework import serializers


class JobPostingSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPosting
        fields = [
            "posting_id",
            "url",
            "company_name",
            "position",
            "main_tasks",
            "requirements",
            "preferred_points",
            "location",
            "district",
            "employment_type",
            "career_min",
            "career_max",
            "created_at",
            "updated_at",
        ]


class ResumeSerializer(serializers.ModelSerializer):
    needs_analysis = serializers.SerializerMethodField()

    class Meta:
        model = Resume
        fields = [
            "id",
            "user_id",
            "content",
            "content_hash",
            "analysis_result",
            "analyzed_at",
            "needs_analysis",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["content_hash", "analyzed_at"]

    def get_needs_analysis(self, obj):
        return obj.needs_analysis()


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

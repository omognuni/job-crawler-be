from job.models import JobPosting
from rest_framework import serializers


class JobPostingSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPosting
        fields = [
            "posting_id",
            "url",
            "company_name",
            "position",
            "category",
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


class JobPostingQuerySerializer(serializers.Serializer):
    """채용 공고 조회용 QuerySerializer"""

    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    career_min = serializers.IntegerField(required=False)
    career_max = serializers.IntegerField(required=False)

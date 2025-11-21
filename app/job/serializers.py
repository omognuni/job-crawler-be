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

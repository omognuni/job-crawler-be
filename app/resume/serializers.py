from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from resume.models import Resume


class ResumeSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Resume
        fields = [
            "id",
            "user_id",
            "title",
            "is_primary",
            "content",
            "content_hash",
            "analysis_result",
            "analyzed_at",
            "last_process_task_id",
            "last_process_task_updated_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "content_hash",
            "analyzed_at",
            "last_process_task_id",
            "last_process_task_updated_at",
        ]

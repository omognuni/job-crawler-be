from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from resume.models import Resume


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

    @extend_schema_field(serializers.BooleanField)
    def get_needs_analysis(self, obj):
        return obj.needs_analysis()

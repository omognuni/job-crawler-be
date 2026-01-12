from job.models import JobPosting
from job.serializers import JobPostingSerializer
from recommendation.domain.scoring import normalize_match_score
from recommendation.models import JobRecommendation, RecommendationPrompt
from rest_framework import serializers


class MatchScoreField(serializers.Field):
    """
    match_score를 항상 정수(int)로 입출력하기 위한 커스텀 필드.
    - to_internal_value: 입력(float/int/str)을 half-up 반올림하여 int로 정규화
    - to_representation: DB에 float로 저장되어 있어도 응답은 int로 반환
    """

    def to_internal_value(self, data):
        return normalize_match_score(data)

    def to_representation(self, value):
        return normalize_match_score(value)


class JobRecommendationReadSerializer(serializers.ModelSerializer):
    """GET 요청용 Serializer - job_posting 전체 정보 포함"""

    job_posting = JobPostingSerializer(read_only=True)
    match_score = MatchScoreField()

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

    # 하위 호환성: 과거 float로 들어오던 match_score도 허용(입력)하되, 저장/응답은 int로 통일
    match_score = MatchScoreField()

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


class RecommendationPromptSerializer(serializers.ModelSerializer):
    """추천 프롬프트 Serializer"""

    class Meta:
        model = RecommendationPrompt
        fields = ["id", "name", "content", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

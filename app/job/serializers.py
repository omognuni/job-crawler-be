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


class CommaSeparatedStringListField(serializers.Field):
    """
    QueryString에서 comma-separated 문자열을 받아 list[str]로 변환하는 필드.

    예:
      tech_stack=python,django  -> ["python", "django"]
      tech_stack=python         -> ["python"]
      tech_stack=              -> []
    """

    def to_internal_value(self, data):
        if data is None:
            return []
        if isinstance(data, list):
            # QueryDict에서 같은 key가 여러 번 들어온 경우를 최대한 안전하게 처리
            items: list[str] = []
            for v in data:
                if v is None:
                    continue
                items.extend(str(v).split(","))
            return [s.strip() for s in items if s.strip()]
        if isinstance(data, str):
            return [s.strip() for s in data.split(",") if s.strip()]
        raise serializers.ValidationError("Invalid list format")

    def to_representation(self, value):
        # QuerySerializer에서는 사용되지 않지만, 일관성을 위해 유지
        if value is None:
            return []
        return list(value)


class JobPostingQuerySerializer(serializers.Serializer):
    """채용 공고 조회용 QuerySerializer"""

    # 기존(Backward compatibility)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    career_min = serializers.IntegerField(required=False)
    career_max = serializers.IntegerField(required=False)

    # 신규(SCRUM-10)
    q = serializers.CharField(required=False, allow_blank=False, max_length=200)
    company = serializers.CharField(required=False, allow_blank=False, max_length=255)
    location = serializers.CharField(required=False, allow_blank=False, max_length=255)
    district = serializers.CharField(required=False, allow_blank=False, max_length=255)
    experience = serializers.IntegerField(required=False, min_value=0)
    tech_stack = CommaSeparatedStringListField(required=False)
    posted_after = serializers.DateField(required=False)
    days = serializers.IntegerField(required=False, min_value=0)
    source = serializers.CharField(required=False, allow_blank=False, max_length=100)
    sort = serializers.ChoiceField(
        required=False,
        choices=[
            ("latest", "latest"),
            ("oldest", "oldest"),
        ],
        default="latest",
    )

    def validate(self, attrs):
        # days vs posted_after: 동시에 오면 혼란이 커서 명시적으로 막는다.
        if attrs.get("days") is not None and attrs.get("posted_after") is not None:
            raise serializers.ValidationError(
                {"days": "Use either days or posted_after, not both."}
            )

        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError(
                {"start_date": "start_date must be <= end_date"}
            )

        career_min = attrs.get("career_min")
        career_max = attrs.get("career_max")
        if (
            career_min is not None
            and career_max is not None
            and career_min > career_max
        ):
            raise serializers.ValidationError(
                {"career_min": "career_min must be <= career_max"}
            )

        # tech_stack 필드가 누락된 경우에도 list로 보장
        if "tech_stack" not in attrs:
            attrs["tech_stack"] = []

        return attrs


class CompanyOptionsQuerySerializer(serializers.Serializer):
    """회사명 옵션(typeahead) 조회용 QuerySerializer"""

    q = serializers.CharField(required=False, allow_blank=True, max_length=255)
    limit = serializers.IntegerField(
        required=False, min_value=1, max_value=100, default=20
    )

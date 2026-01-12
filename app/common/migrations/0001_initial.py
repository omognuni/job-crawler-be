from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.CreateModel(
            name="GeminiModelSetting",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "key",
                    models.CharField(
                        choices=[
                            (
                                "recommendation_evaluator",
                                "추천 평가(Recommendation Evaluator)",
                            ),
                            ("search_plan_builder", "검색 플랜(Search Plan Builder)"),
                            ("resume_analyzer", "이력서 분석(Resume Analyzer)"),
                        ],
                        help_text="어댑터/용도 키 (고유값)",
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "model_name",
                    models.CharField(
                        help_text="Gemini 모델명 (예: gemini-3-flash-preview)",
                        max_length=128,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="비활성화 시 코드 기본값을 사용합니다.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "common_gemini_model_setting",
                "ordering": ["key"],
            },
        ),
    ]

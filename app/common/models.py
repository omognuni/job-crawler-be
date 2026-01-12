from __future__ import annotations

from django.db import models


class GeminiModelSetting(models.Model):
    """
    Gemini 호출 시 사용할 모델명을 Django Admin에서 관리하기 위한 설정 테이블.

    - key: 어떤 유스케이스/어댑터에서 쓰는 모델인지 식별
    - model_name: Google GenAI(Gemini) 모델명 (예: gemini-3-flash-preview)
    """

    class Key(models.TextChoices):
        RECOMMENDATION_EVALUATOR = (
            "recommendation_evaluator",
            "추천 평가(Recommendation Evaluator)",
        )
        SEARCH_PLAN_BUILDER = "search_plan_builder", "검색 플랜(Search Plan Builder)"
        RESUME_ANALYZER = "resume_analyzer", "이력서 분석(Resume Analyzer)"

    key = models.CharField(
        max_length=64,
        unique=True,
        choices=Key.choices,
        help_text="어댑터/용도 키 (고유값)",
    )
    model_name = models.CharField(
        max_length=128,
        help_text="Gemini 모델명 (예: gemini-3-flash-preview)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="비활성화 시 코드 기본값을 사용합니다.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "common_gemini_model_setting"
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.key} -> {self.model_name}"

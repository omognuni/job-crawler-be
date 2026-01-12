from __future__ import annotations

from common.models import GeminiModelSetting
from django.contrib import admin


@admin.register(GeminiModelSetting)
class GeminiModelSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "model_name", "is_active", "updated_at")
    list_filter = ("is_active", "updated_at")
    search_fields = ("key", "model_name")
    ordering = ("key",)

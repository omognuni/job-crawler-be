from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


DEFAULT_GEMINI_MODELS: dict[str, str] = {
    "recommendation_evaluator": "gemini-3-flash-preview",
    "search_plan_builder": "gemini-3-flash-preview",
    "resume_analyzer": "gemini-2.0-flash",
}


def get_gemini_model_name(*, key: str) -> str:
    """
    Django Admin(DB)에서 관리되는 Gemini 모델명을 반환합니다.

    - DB/마이그레이션 미적용/설정 레코드 없음 등 어떤 상황에서도 예외를 외부로 던지지 않고
      안전하게 기본값(DEFAULT_GEMINI_MODELS)으로 fallback 합니다.
    """

    default = DEFAULT_GEMINI_MODELS.get(key)
    if not default:
        # key 오타가 있더라도 서비스가 죽지 않게 방어
        logger.warning(f"Unknown gemini model key: {key!r}. Using hard fallback.")
        return "gemini-3-flash-preview"

    try:
        # cache가 설정되지 않았으면 DummyCache로 동작(항상 miss)하므로 안전합니다.
        from django.core.cache import cache
        from django.core.exceptions import AppRegistryNotReady
        from django.db.utils import OperationalError, ProgrammingError

        cache_key = f"common:gemini_model:{key}"
        cached = cache.get(cache_key)
        if isinstance(cached, str) and cached.strip():
            return cached.strip()

        from common.models import GeminiModelSetting

        setting = (
            GeminiModelSetting.objects.filter(key=key, is_active=True)
            .only("model_name")
            .first()
        )
        if not setting:
            return default

        model_name = (setting.model_name or "").strip()
        if not model_name:
            return default

        # Admin에서 바꿨을 때 어느 정도 빠르게 반영되도록 TTL을 짧게 둡니다.
        cache.set(cache_key, model_name, timeout=60)
        return model_name
    except (OperationalError, ProgrammingError, AppRegistryNotReady) as e:
        logger.debug(f"Gemini model setting unavailable ({key=}): {e}")
        return default
    except Exception as e:
        logger.warning(f"Failed to load gemini model setting ({key=}): {e}")
        return default

import os

import pytest
from config.celery import app as celery_app_instance
from config.celery import debug_task
from django.conf import settings
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError


@pytest.mark.django_db
def test_celery_app_initialization():
    """
    Celery 앱이 정상적으로 임포트되는지 테스트합니다.
    Agent 1이 app/config/celery.py와 app/config/__init__.py를 구현해야 통과합니다.
    """
    try:
        assert celery_app_instance is not None
        assert (
            celery_app_instance.main == "job_crawler"
        )  # Updated based on app/config/celery.py
    except ImportError:
        pytest.fail(
            "Celery app을 'config.celery'에서 임포트할 수 없습니다. Agent 1의 구현이 필요합니다."
        )
    except AttributeError:
        pytest.fail(
            "settings.py에 Celery 설정이 없습니다. Agent 1의 구현이 필요합니다."
        )


@pytest.mark.django_db
@pytest.mark.skipif(
    os.getenv("SKIP_INTEGRATION_TESTS", "false").lower() == "true",
    reason="통합 테스트 스킵 (Redis 서버 필요)",
)
def test_redis_connection():
    """
    settings.py에 설정된 CELERY_BROKER_URL로 Redis에 연결할 수 있는지 테스트합니다.
    Docker compose로 redis 서비스가 실행 중이어야 통과합니다.
    """
    broker_url = getattr(settings, "CELERY_BROKER_URL", None)
    assert broker_url, "settings.CELERY_BROKER_URL이 설정되지 않았습니다."

    try:
        # redis-py는 URL에서 'redis://' 부분을 자동으로 처리합니다.
        redis_client = Redis.from_url(broker_url, socket_connect_timeout=2)
        # PING-PONG으로 연결 확인
        assert redis_client.ping() is True
    except RedisConnectionError as e:
        pytest.skip(
            f"Redis에 연결할 수 없습니다: {e}. Redis 서버가 실행 중인지 확인하세요."
        )
    except Exception as e:
        pytest.fail(f"Redis 연결 중 예상치 못한 오류 발생: {e}")


@pytest.mark.skipif(
    os.getenv("SKIP_INTEGRATION_TESTS", "false").lower() == "true",
    reason="통합 테스트 스킵 (Celery worker 필요)",
)
def test_debug_task_configuration():
    """
    debug_task가 정상적으로 정의되어 있는지 테스트합니다.
    실제 실행은 통합 테스트 환경에서만 수행합니다.
    """
    assert debug_task is not None
    assert callable(debug_task)
    assert hasattr(debug_task, "name")
    assert "debug_task" in debug_task.name


def test_celery_broker_configuration():
    """
    Celery 브로커 설정이 올바르게 구성되어 있는지 테스트합니다.
    """
    broker_url = getattr(settings, "CELERY_BROKER_URL", None)
    result_backend = getattr(settings, "CELERY_RESULT_BACKEND", None)

    assert broker_url is not None, "CELERY_BROKER_URL이 설정되지 않았습니다."
    assert result_backend is not None, "CELERY_RESULT_BACKEND가 설정되지 않았습니다."
    assert "redis" in broker_url, "CELERY_BROKER_URL이 Redis를 사용해야 합니다."
    assert "redis" in result_backend, "CELERY_RESULT_BACKEND가 Redis를 사용해야 합니다."


def test_celery_worker_configuration(celery_eager_mode):
    """
    Celery worker가 eager 모드에서 정상 작동하는지 테스트합니다.
    """
    assert celery_eager_mode is not None
    assert celery_eager_mode.conf.task_always_eager is True


@pytest.mark.django_db
def test_debug_task_execution(celery_eager_mode):
    """
    debug_task를 eager 모드로 실행하여 태스크 실행이 정상 작동하는지 테스트합니다.
    """
    try:
        result = debug_task.apply()
        assert result is not None
        assert result.successful()
    except Exception as e:
        pytest.fail(f"debug_task 실행 중 오류 발생: {e}")


def test_celery_serialization_settings():
    """
    Celery 직렬화 설정이 JSON으로 올바르게 구성되어 있는지 테스트합니다.
    """
    task_serializer = getattr(settings, "CELERY_TASK_SERIALIZER", None)
    result_serializer = getattr(settings, "CELERY_RESULT_SERIALIZER", None)
    accept_content = getattr(settings, "CELERY_ACCEPT_CONTENT", None)

    assert task_serializer == "json", "CELERY_TASK_SERIALIZER가 'json'이어야 합니다."
    assert (
        result_serializer == "json"
    ), "CELERY_RESULT_SERIALIZER가 'json'이어야 합니다."
    assert (
        "application/json" in accept_content
    ), "CELERY_ACCEPT_CONTENT에 'application/json'이 포함되어야 합니다."


def test_celery_timezone_configuration():
    """
    Celery 타임존 설정이 Django TIME_ZONE과 일치하는지 테스트합니다.
    """
    celery_timezone = getattr(settings, "CELERY_TIMEZONE", None)
    django_timezone = getattr(settings, "TIME_ZONE", None)

    assert celery_timezone is not None, "CELERY_TIMEZONE이 설정되지 않았습니다."
    assert (
        celery_timezone == django_timezone
    ), "CELERY_TIMEZONE이 Django TIME_ZONE과 일치해야 합니다."


def test_celery_task_time_limit():
    """
    Celery 태스크 타임아웃 설정이 적절히 구성되어 있는지 테스트합니다.
    """
    time_limit = getattr(settings, "CELERY_TASK_TIME_LIMIT", None)

    assert time_limit is not None, "CELERY_TASK_TIME_LIMIT이 설정되지 않았습니다."
    assert time_limit > 0, "CELERY_TASK_TIME_LIMIT은 양수여야 합니다."
    assert time_limit <= 3600, "CELERY_TASK_TIME_LIMIT이 너무 큽니다 (1시간 이하 권장)."

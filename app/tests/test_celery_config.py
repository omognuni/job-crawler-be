import pytest
from config.celery import (
    app as celery_app_instance,  # Import celery_app_instance and debug_task
)
from config.celery import (
    debug_task,
)
from django.conf import settings
from redis import Redis
from redis.exceptions import ConnectionError


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
def test_redis_connection():
    """
    settings.py에 설정된 CELERY_BROKER_URL로 Redis에 연결할 수 있는지 테스트합니다.
    Docker compose로 redis 서비스가 실행 중이어야 통과합니다.
    """
    broker_url = getattr(settings, "CELERY_BROKER_URL", None)
    assert broker_url, "settings.CELERY_BROKER_URL이 설정되지 않았습니다."

    try:
        # redis-py는 URL에서 'redis://' 부분을 자동으로 처리합니다.
        redis_client = Redis.from_url(broker_url)
        # PING-PONG으로 연결 확인
        assert redis_client.ping() is True
    except ConnectionError as e:
        pytest.fail(
            f"Redis에 연결할 수 없습니다: {e}. Redis 서버가 실행 중인지 확인하세요."
        )
    except Exception as e:
        pytest.fail(f"Redis 연결 중 예상치 못한 오류 발생: {e}")


# New tests using pytest-celery fixtures
def test_celery_worker_starts_and_stops(celery_worker):
    """
    Celery worker가 정상적으로 시작되고 중지되는지 테스트합니다.
    pytest-celery의 celery_worker 픽스처를 사용합니다.
    """
    assert celery_worker.started
    assert not celery_worker.stopped


def test_debug_task_execution(celery_app, celery_worker):
    """
    간단한 더미 태스크(debug_task)가 Celery worker를 통해 정상적으로 실행되는지 테스트합니다.
    """
    # 태스크를 큐에 추가하고 결과를 기다립니다.
    # debug_task는 ignore_result=True이므로 result.get()은 None을 반환합니다.
    # 대신 태스크가 성공적으로 실행되었는지 확인합니다.
    result = debug_task.delay()
    assert result.get(timeout=10) is None  # debug_task has ignore_result=True
    assert result.successful()

# app/conftest.py
"""
pytest fixtures for Celery testing
"""
import os

import pytest
from celery import Celery


@pytest.fixture(scope="session")
def celery_config():
    """
    Celery 테스트용 설정을 제공합니다.
    """
    return {
        "broker_url": os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
        "result_backend": os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
        "task_always_eager": False,
        "task_eager_propagates": True,
        "accept_content": ["json"],
        "task_serializer": "json",
        "result_serializer": "json",
    }


@pytest.fixture(scope="session")
def celery_app(celery_config):
    """
    테스트용 Celery 앱 인스턴스를 제공합니다.
    """
    from config.celery import app

    app.config_from_object(celery_config)
    return app


@pytest.fixture
def celery_worker(celery_app):
    """
    테스트용 Celery worker를 제공합니다.
    """
    celery_app.conf.update(task_always_eager=True)
    return celery_app


@pytest.fixture
def celery_eager_mode(celery_app):
    """
    Eager 모드로 Celery를 설정합니다 (동기 실행).
    """
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    yield celery_app
    celery_app.conf.task_always_eager = original_eager

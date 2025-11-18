FROM python:3.13-slim

WORKDIR /workspace

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENV HOME=/workspace

RUN apt-get update && apt-get install -y gcc python3-dev && rm -rf /var/lib/apt/lists/*
RUN pip install uv

COPY pyproject.toml .
COPY uv.lock .
COPY ./app /workspace/app

RUN mkdir -p /workspace/.venv /workspace/.uv/cache

RUN chown -R 1000:1000 /workspace

USER 1000:1000

ENV PYTHONPATH="/workspace"
ENV UV_CACHE_DIR="/workspace/.uv/cache"

RUN uv sync --frozen && uv cache prune --ci

WORKDIR /workspace/app

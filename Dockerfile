FROM python:3.13-slim

WORKDIR /workspace

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y gcc python3-dev && rm -rf /var/lib/apt/lists/*
RUN pip install uv

COPY pyproject.toml .
COPY uv.lock .

RUN uv sync --frozen && uv cache prune --ci

COPY ./app /workspace/app

WORKDIR /workspace/app

ENV PYTHONPATH="/workspace"
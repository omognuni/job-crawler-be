# Stage 1: Builder
FROM python:3.13-slim AS builder

WORKDIR /workspace

# 빌드 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 의존성 파일 복사
COPY pyproject.toml uv.lock ./

# 의존성 설치
# --mount=type=cache: 빌드 캐시 활용
# --no-install-project: 소스 코드 없이 의존성만 설치하여 레이어 캐싱 최적화
ENV UV_COMPILE_BYTECODE=1
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Stage 2: Runtime
FROM python:3.13-slim

WORKDIR /workspace

# uv 복사 (런타임에서 uv run 사용 시 필요)
COPY --from=builder /bin/uv /bin/uv

# 가상 환경 복사
COPY --from=builder /workspace/.venv /workspace/.venv

# 환경 변수 설정
ENV PATH="/workspace/.venv/bin:$PATH"
ENV PYTHONPATH="/workspace"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 사용자 생성 (UID 1000으로 명시하여 docker-compose의 user 설정과 호환)
RUN useradd -m -u 1000 appuser

# 소스 코드 복사
COPY --chown=appuser:appuser ./app /workspace/app

# 작업 디렉토리를 app으로 변경 (manage.py 실행을 위해)
WORKDIR /workspace/app

USER appuser

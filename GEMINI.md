# GEMINI Context: Job Crawler Backend

## 0. 에이전트 상호작용 가이드라인

**핵심 지침:** 이 프로젝트는 Docker Compose와 `uv` 가상 환경을 중심으로 구성되어 있습니다. 모든 명령어는 이 컨텍스트를 고려하여 실행되어야 합니다.

*   **명령어 실행 컨텍스트:**
    *   **Docker 환경:** `docker compose exec app <명령어>` 또는 `docker compose run --rm app <명령어>`를 사용하여 `app` 서비스 컨테이너 내부에서 명령을 실행하는 것을 기본으로 합니다.
    *   **가상 환경:** 컨테이너 내부에서는 `uv`가 패키지 관리를 위해 사용됩니다. 따라서 Python 스크립트나 Django 관리 명령어는 `uv run <명령어>` 형태로 실행해야 합니다. 예: `uv run python manage.py migrate`.
*   **계획 작성 지침:**
    *   계획을 작성할 때, 각 항목의 진행 상태를 명확히 표시하기 위해 `[ ]` (미완료) 및 `[x]` (완료) 체크박스 표기법을 사용해야 합니다.
*   **결론:** **항상 Docker와 가상환경 설정을 고려하여 올바른 명령어를 구성해야 합니다.** 로컬 쉘에서 직접 `python manage.py`를 실행하는 것은 올바른 방법이 아닙니다.

---

## 1. 전역 설정 개요

이 프로젝트의 대부분의 중요한 설정은 환경 변수를 통해 관리됩니다. 이는 다양한 배포 환경(로컬 개발, 스테이징, 프로덕션 등)에서 유연하게 설정을 변경할 수 있도록 돕고, 민감한 정보(예: API 키, 데이터베이스 비밀번호)를 코드베이스 외부에서 안전하게 관리할 수 있게 합니다.

주요 설정은 `app/config/settings.py` 파일에 정의되어 있으며, 여기서 환경 변수를 로드하고 기본값을 설정합니다.

## 2. 핵심 환경 변수 (Core Environment Variables)

다음은 프로젝트 운영에 필수적인 주요 환경 변수 목록입니다. `.env` 파일 또는 배포 환경에서 설정되어야 합니다.

*   `SECRET_KEY`: Django 프로젝트의 보안을 위한 고유한 비밀 키입니다. **필수적으로 설정해야 합니다.**
*   `API_SECRET_KEY`: 특정 API 엔드포인트의 추가 인증을 위한 비밀 키입니다. **필수적으로 설정해야 합니다.**
*   `DEBUG`: Django의 디버그 모드를 활성화(`True`) 또는 비활성화(`False`)합니다. 프로덕션 환경에서는 `False`로 설정해야 합니다. (기본값: `False`)
*   `ALLOWED_HOSTS`: Django 애플리케이션이 응답할 수 있는 호스트 이름 목록입니다. 콤마(`,`)로 구분된 문자열로 제공됩니다. (기본값: `localhost,127.0.0.1,0.0.0.0`)
*   `SLACK_WEBHOOK_URL`: 특정 알림(예: 에러 로깅)을 Slack으로 전송하기 위한 웹훅 URL입니다. (선택 사항)
*   `GOOGLE_API_KEY`: CrewAI 및 Gemini LLM 호출에 사용되는 Google API 키입니다. (`README.md`에 명시됨)
*   `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`: 다른 LLM을 사용할 경우 설정합니다. (`README.md`에 명시됨)

## 3. 데이터베이스 설정 (Database Configuration)

### 3.1 PostgreSQL (관계형 데이터베이스)

Django의 주 데이터베이스로 사용되며, 다음 환경 변수를 통해 연결 정보를 설정합니다.

*   `DB_NAME`: PostgreSQL 데이터베이스 이름 (필수)
*   `DB_USER`: PostgreSQL 사용자 이름 (기본값: `postgres`)
*   `DB_PASS`: PostgreSQL 사용자 비밀번호 (기본값: `postgres`)
*   `DB_HOST`: PostgreSQL 서버 호스트 (기본값: `localhost`)
*   `DB_PORT`: PostgreSQL 서버 포트 (기본값: `5432`)

### 3.2 Neo4j (그래프 데이터베이스)

기술 스택, 회사, 직무 간의 관계를 모델링하는 데 사용됩니다.

*   `NEO4J_URI`: Neo4j 데이터베이스 연결 URI (기본값: `bolt://neo4j:7687`)
*   `NEO4J_USER`: Neo4j 사용자 이름 (기본값: `neo4j`)
*   `NEO4J_PASSWORD`: Neo4j 사용자 비밀번호입니다. **필수적으로 설정해야 합니다.**

### 3.3 ChromaDB (벡터 데이터베이스)

채용 공고 및 이력서 임베딩의 의미 기반 검색을 위해 사용됩니다.

*   ChromaDB의 호스트와 포트는 `app/common/vector_db.py` 파일에 `chromadb:8000`으로 하드코딩되어 있습니다. 이는 주로 Docker Compose 환경에서 서비스 이름(`chromadb`)을 통해 해결됩니다.

## 4. 비동기 작업 (Celery) 설정

백그라운드에서 실행되는 비동기 작업(예: LLM 분석, 데이터 임베딩)을 처리하기 위해 Celery가 사용됩니다. Redis를 브로커 및 결과 저장소로 사용합니다.

*   `CELERY_BROKER_URL`: Celery 브로커(Redis) 연결 URL (기본값: `redis://redis:6379/0`)
*   `CELERY_RESULT_BACKEND`: Celery 작업 결과 저장소(Redis) 연결 URL (기본값: `redis://redis:6379/0`)

그 외 Celery 관련 설정들은 `app/config/settings.py`에 직접 정의되어 있습니다 (`CELERY_ACCEPT_CONTENT`, `CELERY_TASK_SERIALIZER`, `CELERY_RESULT_SERIALIZER`, `CELERY_TIMEZONE`, `CELERY_TASK_TIME_LIMIT` 등).

## 5. 기타 중요한 설정

*   **DRF & JWT 인증:** `REST_FRAMEWORK` 및 `SIMPLE_JWT` 설정을 통해 API 인증 및 JWT 토큰 관리를 구성합니다.
*   **API 문서 (Spectacular):** `drf-spectacular`를 사용하여 OpenAPI 스키마 및 Swagger/Redoc UI를 자동 생성합니다. `SPECTACULAR_SETTINGS`에서 제목, 설명, 버전 등을 설정합니다.
*   **CORS (교차 출처 리소스 공유):** `CORS_ALLOWED_ORIGINS` 환경 변수를 통해 허용되는 출처를 제어하며, `CORS_ALLOW_CREDENTIALS` 등의 설정이 적용됩니다.
*   **보안 헤더:** `SECURE_BROWSER_XSS_FILTER`, `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS` 등 다양한 보안 관련 헤더가 설정되어 있습니다. 프로덕션 환경에서는 SSL/TLS 관련 설정(`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` 등)도 활성화해야 합니다.
*   **정적 파일:** `STATIC_URL`, `STATIC_ROOT` 및 `whitenoise`를 사용하여 정적 파일이 서빙됩니다.
*   **국제화:** `LANGUAGE_CODE`는 `ko-kr`, `TIME_ZONE`은 `Asia/Seoul`로 설정되어 있습니다.

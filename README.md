# Job Crawler Backend

Django REST Framework 기반 채용 공고 분석 및 추천 시스템

## 필수 요구사항

### 1. Python 환경
- Python >= 3.12 (3.12 또는 3.13 권장, 3.14는 일부 패키지 미지원)
- uv (패키지 매니저)

### 2. 의존성 설치

```bash
# uv를 사용하는 경우
uv sync

# 또는 pip 사용
pip install -e .
```

### 3. 환경 변수 설정

배포 서버에 다음 환경 변수를 설정해야 합니다:

```bash
# Django 설정
export SECRET_KEY="your-secret-key"
export DEBUG=False
export ALLOWED_HOSTS="your-domain.com"

# LLM API Key (아래 중 하나만 설정)
export OPENAI_API_KEY="sk-..."           # OpenAI (GPT-4 등)
export ANTHROPIC_API_KEY="sk-ant-..."   # Anthropic (Claude)
export GOOGLE_API_KEY="..."             # Google (Gemini)
```

## 배포 시 필요한 것

### ✅ 필요한 것:
- Python 실행 환경
- pip/uv로 설치된 Python 패키지들
- 환경 변수로 설정된 API Key
- 인터넷 연결 (LLM API 호출용)

### ❌ 필요하지 않은 것:
- Claude Desktop, Gemini CLI 같은 별도 프로그램
- GPU, 로컬 LLM 모델
- Docker (선택사항)

## 구조 설명

```
배포 서버
  │
  ├── Django App (Python 코드)
  │     ├── CrewAI (Python 라이브러리)
  │     │     └── HTTP 요청 →→→ 외부 LLM API 서버
  │     ├── ChromaDB (Vector DB)
  │     └── Neo4j (Graph DB)
  │
  └── PostgreSQL/MySQL (관계형 DB)
```

**CrewAI는 Python 패키지**이며, API Key를 통해 **외부 LLM 서버에 HTTP 요청**을 보냅니다.
**ChromaDB**는 채용 공고 및 이력서의 의미 기반 검색을 위한 벡터 임베딩을 저장하고 관리합니다.
**Neo4j**는 기술 스택, 회사, 직무 간의 복잡한 관계를 저장하고 분석하여 정교한 추천 로직을 지원합니다.

## 실행 방법

### 로컬 개발 환경 (Docker Compose 사용)

ChromaDB, Neo4j, PostgreSQL을 포함한 전체 개발 환경을 Docker Compose로 실행합니다.

1.  **Docker Desktop 설치**: Docker Desktop이 설치되어 있고 실행 중인지 확인합니다.
2.  **환경 변수 파일 생성**: `.env` 파일을 프로젝트 루트에 생성하고 필요한 환경 변수를 설정합니다. (예: `DB_USER`, `DB_PASS`, `DB_NAME`, `GOOGLE_API_KEY` 등)
3.  **서비스 실행**:
    ```bash
    docker compose up --build
    ```
    (백그라운드 실행: `docker compose up --build -d`)
4.  **마이그레이션 및 데이터 처리**: `app` 컨테이너가 실행된 후, 다음 명령을 실행하여 데이터베이스 마이그레이션을 적용하고 초기 데이터를 처리합니다.
    ```bash
    docker exec -it app sh -c "uv run python manage.py migrate"
    docker exec -it app sh -c "uv run python manage.py process_data --all"
    ```
    (이 명령은 `JobPosting` 및 `Resume` 데이터를 벡터/그래프 DB에 임베딩하고, `JobPosting`의 `skills_required`, `skills_preferred` 필드를 채웁니다.)

### 프로덕션 환경

`docker-compose.prod.yml` 파일을 사용하여 프로덕션 환경을 배포할 수 있습니다. `.env.prod` 파일을 적절히 설정해야 합니다.

```bash
# 프로덕션 환경 빌드 및 실행
docker compose -f docker-compose.prod.yml up --build -d
```

### 수동 실행 (Docker 없이)

```bash
# 개발 환경
uv run python manage.py runserver

# 프로덕션 환경
uv run gunicorn app.config.wsgi:application
```

## Agent 동작 방식

1.  **이력서 분석 (Resume Analysis)**:
    *   `Get resume tool`은 이력서 내용을 기반으로 `skills`, `career_years`, `strengths` 등의 구조화된 정보를 추출합니다. 이 과정은 LLM의 직접적인 개입 없이 내부 로직(`_extract_resume_details`)을 통해 처리되어 효율성을 높입니다.
2.  **채용 공고 검색 (Job Posting Search)**:
    *   이력서 분석 결과를 바탕으로 `Vector Search Job Postings Tool`을 사용하여 벡터 DB에서 의미적으로 유사한 채용 공고를 검색합니다.
    *   각 채용 공고는 `skills_required` (필수 기술 스택) 및 `skills_preferred` (우대 기술 스택)와 같은 구조화된 스킬 정보를 포함하고 있어, LLM이 원문 텍스트에서 정보를 추출할 필요 없이 직접 활용할 수 있습니다.
3.  **매칭 및 추천 (Matching & Recommendation)**:
    *   필터링된 채용 공고 목록과 이력서 분석 결과를 정밀하게 비교하여 매칭 점수를 계산하고, 최종 Top 10 추천 공고를 선정합니다. 이 과정에서 그래프 DB를 활용하여 기술 스택 간의 관계나 경력 경로의 유사성 등을 더욱 정교하게 분석할 수 있습니다.
    *   `Save recommendations tool`을 사용하여 추천 결과를 DB에 저장합니다.

**핵심 변경 사항**:
-   **LLM 의존도 감소**: 이력서 및 채용 공고에서 핵심 정보를 추출하는 과정에서 LLM의 직접적인 역할을 최소화하고, 구조화된 데이터베이스(Vector DB, Graph DB)와 내부 로직을 적극 활용합니다.
-   **효율성 및 일관성 향상**: 데이터 추출 및 검색 과정의 효율성이 증가하고, LLM의 비결정성으로 인한 결과의 편차를 줄여 일관된 추천 품질을 제공합니다.

**별도의 Agent 프로그램 설치 불필요 - Python 라이브러리로 모두 처리됩니다.**

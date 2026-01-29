# Job Crawler Backend

AI-Free 실시간 채용 공고 추천 시스템

## 📋 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [아키텍처](#아키텍처)
- [기술 스택](#기술-스택)
- [설치 및 실행](#설치-및-실행)
- [API 문서](#api-문서)
- [테스트](#테스트)
- [CI/CD](#cicd)
- [프로젝트 구조](#프로젝트-구조)

## 개요

Job Crawler Backend는 하이브리드 추천 시스템을 사용하여 사용자에게 최적의 채용 공고를 추천하는 서비스입니다.

### 핵심 특징

- **AI-Free 추천 엔진**: LLM 없이 벡터 유사도 + 스킬 그래프 매칭
- **실시간 처리**: 500ms 이내 추천 생성
- **Service Layer 패턴**: 비즈니스 로직 분리로 높은 유지보수성
- **비동기 처리**: Celery를 통한 백그라운드 작업 처리

## 주요 기능

### 1. 채용 공고 관리
- CRUD API
- 자동 스킬 추출 (104개 기술 스택)
- 벡터 임베딩 생성 (ChromaDB)
- 스킬 그래프 구축 (Neo4j)

### 2. 이력서 분석
- LLM 기반 이력서 분석 (Gemini)
- 경력 연차 계산
- 핵심 강점 추출
- 임베딩 생성

### 3. 하이브리드 추천
- **1단계**: 벡터 유사도 검색 (ChromaDB) - 50개 후보
- **2단계**: 스킬 그래프 매칭 (Neo4j) - 20개 정제
- **3단계**: 규칙 기반 점수 계산 - Top 10 추천

### 4. 검색
- 벡터 유사도 검색
- 하이브리드 검색 (벡터 + 스킬)

## 아키텍처

Hexagonal(Ports & Adapters) + Clean Architecture 스타일을 적용합니다.

```
┌─────────────────────────────────────────────────────────────┐
│                      Presentation Layer                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Views (Thin Controller) - HTTP 처리만 담당         │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Services (Thin Facade) → UseCases (Orchestration)  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Domain Layer                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Pure Logic (점수 계산, 정규화 등) - Django/I/O 금지 │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Infrastructure Layer                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │    Ports     │  │   Adapters   │  │   External   │       │
│  │  (Interface) │→ │   (Impl)     │→ │   Services   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                              │
│  PostgreSQL │ ChromaDB │ Neo4j │ Redis │ Gemini             │
└─────────────────────────────────────────────────────────────┘
```

### 의존 방향 (단방향)

```
views → services → application/usecases → ports → adapters
```

### 앱 구조

```
app/
├── job/              # 채용 공고 관리
├── resume/           # 이력서 관리
├── recommendation/   # 추천 시스템
├── search/           # 검색 기능
├── skill/            # 스킬 추출
├── user/             # 사용자 관리 (Google OAuth)
└── common/           # 공통 인프라
    ├── ports/        # 인터페이스 정의
    └── adapters/     # 구체 구현 (Chroma, Neo4j, Gemini 등)
```

## 기술 스택

### Backend
- **Framework**: Django 5.2, Django REST Framework
- **Language**: Python 3.12+
- **Task Queue**: Celery + Redis

### Databases
- **RDBMS**: PostgreSQL
- **Vector DB**: ChromaDB (Sentence Transformers)
- **Graph DB**: Neo4j

### AI/ML
- **LLM**: Google Gemini 2.0 Flash
- **Embedding**: Sentence Transformers (all-MiniLM-L6-v2)
- **Skill Extraction**: Regex-based (LLM-Free)

### Infrastructure
- **Containerization**: Docker, Docker Compose
- **Package Manager**: uv
- **API Documentation**: drf-spectacular (OpenAPI 3.0)

## 설치 및 실행

### 환경 변수 설정

`.env` 파일 생성:

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/job_crawler

# Redis
REDIS_URL=redis://localhost:6379/0

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Google AI
GOOGLE_API_KEY=your-google-api-key

# Google OAuth (Login/Signup)
# - 기능 플래그: OFF면 OAuth 엔드포인트가 404로 비활성화됩니다.
GOOGLE_OAUTH_ENABLED=False
GOOGLE_OAUTH_CLIENT_ID=your-google-oauth-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-google-oauth-client-secret
# 허용된 FE callback URL (정확 일치, 쉼표로 구분)
GOOGLE_OAUTH_ALLOWED_REDIRECT_URIS=http://localhost:3000/auth/google/callback
# state/PKCE 유효기간(초)
GOOGLE_OAUTH_STATE_TTL_SECONDS=600

# API
API_SECRET_KEY=your-api-secret-key
```

### Docker로 실행

```bash
# 컨테이너 시작
docker-compose up -d

# 마이그레이션
docker exec -it job-crawler-web uv run python manage.py migrate

# 슈퍼유저 생성
docker exec -it job-crawler-web uv run python manage.py createsuperuser

# Celery worker 시작
docker exec -it job-crawler-celery celery -A config worker -l info
```

### 로컬 개발 환경

```bash
# uv 설치
pip install uv

# 의존성 설치
uv sync

# 가상환경 활성화
source .venv/bin/activate

# 마이그레이션
python manage.py migrate

# 서버 실행
python manage.py runserver

# Celery worker (별도 터미널)
celery -A config worker -l info
```

## API 문서

### Base URL
```
http://localhost:8000/api/v1/
```

### 주요 엔드포인트

#### 채용 공고
```
GET    /jobs/                  # 목록
POST   /jobs/                  # 생성
GET    /jobs/{id}/             # 조회
PUT    /jobs/{id}/             # 수정
DELETE /jobs/{id}/             # 삭제
```

#### 이력서
```
GET    /resumes/               # 목록
POST   /resumes/               # 생성
GET    /resumes/{user_id}/     # 조회
PATCH  /resumes/{user_id}/     # 수정
DELETE /resumes/{user_id}/     # 삭제
```

#### 추천
```
GET    /recommendations/                          # 저장된 추천 목록
GET    /recommendations/for-user/{user_id}/       # 실시간 추천 생성
POST   /recommendations/                          # 추천 저장
DELETE /recommendations/{id}/                     # 추천 삭제
```

#### 검색
```
GET    /search/?query={text}&limit={int}          # 벡터 검색
POST   /search/hybrid/                            # 하이브리드 검색
```

#### 스킬
```
GET    /skills/related/{skill_name}/              # 스킬별 채용 공고
```

### Swagger UI
```
http://localhost:8000/api/v1/schema/swagger-ui/
```

## 테스트

### 전체 테스트 실행

```bash
# Docker 환경
docker exec -it job-crawler-web uv run pytest

# 로컬 환경
pytest
```

### 테스트 커버리지

```bash
# 커버리지 측정
pytest --cov=app --cov-report=html

# 결과 확인
open htmlcov/index.html
```

### 특정 앱 테스트

```bash
# Job 앱
pytest app/job/tests/

# Resume 앱
pytest app/resume/tests/

# Recommendation 앱
pytest app/recommendation/tests/
```

### 성능 테스트

```bash
pytest app/tests/performance/ -v
```

## CI/CD

GitHub Actions를 통해 자동화된 테스트 및 배포 파이프라인을 운영합니다.

### 파이프라인 구조

```
PR 생성/업데이트 → Test Job (pytest) → ✅ 통과 시 Merge 가능
                                       ❌ 실패 시 Merge 차단

main 브랜치 Push → Test Job → Build & Push (Docker) → Deploy (SSH)
                      ↓
                   ❌ 실패 시 배포 중단
```

### 워크플로우 (`deploy.yml`)

| Job | 트리거 | 설명 |
|-----|--------|------|
| `test` | PR, Push (main) | PostgreSQL 서비스 + pytest 실행 |
| `build-and-deploy` | Push (main) | Docker 이미지 빌드 → ghcr.io 푸시 → SSH 배포 |

### 테스트 환경

- **DB**: PostgreSQL 15 (서비스 컨테이너)
- **Python**: 3.12 (uv로 의존성 설치)
- **Runner**: ubuntu-latest

### 배포 환경

- **Registry**: GitHub Container Registry (ghcr.io)
- **Target**: SSH 서버 (docker-compose.prod.yml)
- **Health Check**: 배포 후 `/health/` 엔드포인트 확인

## 프로젝트 구조

```
job-crawler-be/
├── .github/
│   └── workflows/
│       └── deploy.yml         # CI/CD 파이프라인
│
├── app/
│   ├── job/                   # 채용 공고 앱
│   │   ├── application/       # UseCases
│   │   │   ├── container.py   # DI 조립
│   │   │   └── usecases/
│   │   ├── tests/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── services.py        # Thin Facade
│   │   ├── serializers.py
│   │   ├── tasks.py           # Celery 작업
│   │   └── urls.py
│   │
│   ├── resume/                # 이력서 앱
│   │   ├── application/
│   │   │   ├── container.py
│   │   │   └── usecases/
│   │   ├── tests/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── services.py
│   │   ├── tasks.py
│   │   └── urls.py
│   │
│   ├── recommendation/        # 추천 앱
│   │   ├── application/
│   │   │   ├── container.py
│   │   │   └── usecases/
│   │   ├── domain/            # 순수 로직 (점수 계산 등)
│   │   ├── tests/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── services.py
│   │   └── urls.py
│   │
│   ├── user/                  # 사용자/OAuth 앱
│   │   ├── application/
│   │   │   ├── container.py
│   │   │   └── usecases/
│   │   ├── domain/            # OAuth 로직
│   │   ├── ports/             # 인터페이스
│   │   ├── adapters/          # 구현
│   │   ├── tests/
│   │   └── ...
│   │
│   ├── skill/                 # 스킬 추출 앱
│   │   ├── tests/
│   │   ├── services.py
│   │   └── urls.py
│   │
│   ├── search/                # 검색 앱
│   │   ├── tests/
│   │   ├── services.py
│   │   └── urls.py
│   │
│   ├── common/                # 공통 인프라
│   │   ├── ports/             # 인터페이스 정의
│   │   │   ├── vector_store.py
│   │   │   ├── graph_store.py
│   │   │   ├── resume_analyzer.py
│   │   │   └── ...
│   │   ├── adapters/          # 구체 구현
│   │   │   ├── chroma_vector_store.py
│   │   │   ├── neo4j_graph_store.py
│   │   │   ├── google_genai_resume_analyzer.py
│   │   │   └── ...
│   │   ├── middleware.py      # Request-ID 등
│   │   └── ...
│   │
│   ├── config/                # 설정
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── celery.py
│   │
│   ├── conftest.py            # pytest 공통 fixture
│   └── pytest.ini
│
├── docker-compose.yml         # 개발 환경
├── docker-compose.prod.yml    # 프로덕션 환경
├── Dockerfile
├── pyproject.toml
└── README.md
```

## 개발 가이드

### Service Layer 패턴

모든 비즈니스 로직은 Service Layer에 구현합니다:

```python
# ❌ Bad: View에 비즈니스 로직
class JobPostingViewSet(ModelViewSet):
    def create(self, request):
        # 복잡한 비즈니스 로직...
        pass

# ✅ Good: Service에 비즈니스 로직
class JobPostingViewSet(ModelViewSet):
    def create(self, request):
        posting = JobService.create_job_posting(data)
        return Response(serializer.data)
```

### Thin Controller 원칙

View는 HTTP 요청/응답 처리만 담당:

```python
def create(self, request):
    try:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Service에 위임
        job_posting = JobService.create_job_posting(
            serializer.validated_data
        )

        return Response(
            self.get_serializer(job_posting).data,
            status=status.HTTP_201_CREATED
        )
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        return Response(
            {"error": "Failed to create"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
```

## 성능 지표

- **추천 생성**: < 500ms (p95)
- **검색**: < 300ms (p95)
- **CRUD API**: < 200ms (p95)
- **스킬 추출**: < 100ms

## 라이선스

This project is licensed under the MIT License.

## 기여

Pull Request는 언제나 환영입니다!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 문의

프로젝트에 대한 문의사항이 있으시면 이슈를 남겨주세요.

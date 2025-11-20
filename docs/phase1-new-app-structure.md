# Phase 1.3: 새로운 앱 구조 생성 결과

## 📊 생성 일자
2025년 11월 20일

## 1. 생성된 앱 목록

### 1.1 전체 앱 구조
```
app/
├── skill/              # 스킬 추출 및 관리
├── search/             # 벡터 검색 기능
├── job_posting/        # 채용 공고 관리
├── resume/             # 이력서 관리
└── recommendation/     # 추천 엔진
```

### 1.2 각 앱별 생성된 파일

#### `skill/` - 스킬 추출 및 관리
```
skill/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── views.py
├── tests.py
├── migrations/
│   └── __init__.py
├── services.py         # ✨ 추가 생성
└── urls.py             # ✨ 추가 생성
```

**책임**:
- LLM-Free 스킬 추출 로직
- 마스터 스킬 목록 관리
- 스킬 기반 채용공고 검색

**이동 예정 코드**:
- `job/skill_extractor.py` → `skill/services.py`
- `RelatedJobsView` → `skill/views.py`

#### `search/` - 벡터 검색 기능
```
search/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── views.py
├── tests.py
├── migrations/
│   └── __init__.py
├── services.py         # ✨ 추가 생성
└── urls.py             # ✨ 추가 생성
```

**책임**:
- ChromaDB 벡터 유사도 검색
- 하이브리드 검색 (vector + graph)
- 검색 결과 랭킹

**이동 예정 코드**:
- `JobSearchView` → `search/views.py`
- `agent.tools.vector_search_job_postings_tool` → `search/services.py`

#### `job_posting/` - 채용 공고 관리
```
job_posting/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── views.py
├── tests.py
├── migrations/
│   └── __init__.py
├── services.py         # ✨ 추가 생성
├── tasks.py            # ✨ 추가 생성 (Celery)
└── urls.py             # ✨ 추가 생성
```

**책임**:
- JobPosting 모델 관리
- CRUD API 제공
- 스킬 추출 및 임베딩
- Neo4j/ChromaDB 연동

**이동 예정 코드**:
- `job/models.py::JobPosting` → `job_posting/models.py`
- `JobPostingViewSet` → `job_posting/views.py`
- `JobPostingSerializer` → `job_posting/serializers.py`
- `process_job_posting` task → `job_posting/tasks.py`

#### `resume/` - 이력서 관리
```
resume/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── views.py
├── tests.py
├── migrations/
│   └── __init__.py
├── services.py         # ✨ 추가 생성
├── tasks.py            # ✨ 추가 생성 (Celery)
└── urls.py             # ✨ 추가 생성
```

**책임**:
- Resume 모델 관리
- CRUD API 제공
- 이력서 분석 (LLM)
- 경력/스킬 추출
- ChromaDB 임베딩

**이동 예정 코드**:
- `job/models.py::Resume` → `resume/models.py`
- `ResumeViewSet` → `resume/views.py`
- `ResumeSerializer` → `resume/serializers.py`
- `process_resume` task → `resume/tasks.py`

#### `recommendation/` - 추천 엔진
```
recommendation/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── views.py
├── tests.py
├── migrations/
│   └── __init__.py
├── services.py         # ✨ 추가 생성
└── urls.py             # ✨ 추가 생성
```

**책임**:
- JobRecommendation 모델 관리
- 하이브리드 추천 엔진 (Vector + Graph)
- 매칭 점수 계산
- 추천 이유 생성

**이동 예정 코드**:
- `job/models.py::JobRecommendation` → `recommendation/models.py`
- `JobRecommendationViewSet` → `recommendation/views.py`
- `job/recommender.py` → `recommendation/services.py`
- `RecommendationsView` → `recommendation/views.py`

## 2. INSTALLED_APPS 등록

### 2.1 settings.py 업데이트
```python
INSTALLED_APPS = [
    # Django 기본 앱
    "django.contrib.admin",
    "django.contrib.auth",
    ...
    # 서드파티 앱
    "rest_framework",
    "corsheaders",
    ...
    # 기존 앱
    "agent",  # TODO: deprecated 예정
    "job.apps.JobConfig",  # TODO: Phase 2 완료 후 제거
    "user",
    # 새로운 앱 (Phase 1.3에서 생성) ✨
    "skill",
    "search",
    "job_posting",
    "resume",
    "recommendation",
]
```

### 2.2 Django Check 통과
```bash
$ docker exec app bash -c "uv run python manage.py check"
System check identified no issues (0 silenced).
```

## 3. 서비스 레이어 템플릿

각 앱에 `services.py` 파일을 생성하여 비즈니스 로직을 캡슐화할 준비를 했습니다.

### 3.1 Service 클래스 패턴
```python
# skill/services.py
class SkillExtractionService:
    """
    스킬 추출 서비스

    LLM-Free 방식으로 텍스트에서 기술 스택을 추출합니다.
    """

    def __init__(self):
        pass

    # TODO: job/skill_extractor.py에서 로직 이동 예정
```

**장점**:
- 뷰에서 비즈니스 로직 분리 (Thin Controller 패턴)
- 재사용 가능한 서비스 메서드
- 테스트 용이성 증가
- 의존성 주입 가능

### 3.2 Celery Tasks 템플릿
```python
# job_posting/tasks.py
from celery import shared_task

@shared_task(bind=True, max_retries=3, name='job_posting.process_job_posting')
def process_job_posting(self, posting_id: int):
    """
    채용 공고를 처리하는 Celery 태스크

    1. 스킬 추출
    2. 임베딩 생성
    3. ChromaDB 저장
    4. Neo4j 관계 생성
    """
    pass
```

**주의사항**:
- `name` 파라미터로 명시적 태스크 이름 지정 (경로 변경 대비)
- 기존 큐에 있는 태스크와 충돌 방지
- Worker 재시작 필요

### 3.3 URL 라우팅 템플릿
```python
# job_posting/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

# TODO: ViewSet 이동 후 라우터 설정
# router = DefaultRouter()
# router.register(r"", JobPostingViewSet, basename="jobposting")

urlpatterns = [
    # path("", include(router.urls)),
]
```

## 4. 의존성 그래프

```
┌──────────────┐
│   skill      │  (가장 독립적)
└──────────────┘
       ↑
       │ uses
┌──────────────┐
│   search     │
└──────────────┘
       ↑
       │ uses
┌──────────────┐     ┌──────────────┐
│ job_posting  │     │   resume     │
└──────────────┘     └──────────────┘
       ↑                    ↑
       └──────┬─────────────┘
              │ depends on both
       ┌──────────────────┐
       │  recommendation  │  (가장 의존적)
       └──────────────────┘
```

**마이그레이션 순서** (Phase 2):
1. `skill` - 가장 독립적
2. `search`
3. `job_posting`, `resume` (병렬 가능)
4. `recommendation` - 가장 의존적

## 5. 수정된 파일

### 5.1 agent/tools.py 수정
**문제**: `from job.signals import SKILL_LIST, _extract_resume_details` 에러
- `job.signals` 모듈이 존재하지 않음

**해결책**:
```python
# Before
from job.signals import SKILL_LIST, _extract_resume_details

# After
# TODO: agent 앱은 deprecated 예정 - signals.py 제거됨
# from job.signals import SKILL_LIST, _extract_resume_details

# _extract_resume_details 호출 대신 Celery 태스크 사용
from job.tasks import process_resume
process_resume.delay(user_id)
```

**영향**:
- agent 앱은 deprecated 예정이므로 임시 수정
- Phase 2 완료 후 agent 앱 전체 제거 예정

### 5.2 config/settings.py 수정
- 새로운 5개 앱 INSTALLED_APPS에 등록
- 기존 앱에 TODO 주석 추가

## 6. 다음 단계 (Phase 2)

### 6.1 마이그레이션 순서
```
Phase 2.1: skill app 분리
    ↓
Phase 2.2: search app 분리
    ↓
Phase 2.3: job_posting app 분리
    ↓
Phase 2.4: resume app 분리
    ↓
Phase 2.5: recommendation app 분리
```

### 6.2 각 Phase별 작업
1. **모델 이동** (해당 시)
   - 기존 테이블명 유지 (`Meta.db_table`)
   - `--fake` 마이그레이션

2. **ViewSet/Serializer 이동**
   - API 엔드포인트 유지
   - URL 라우팅 업데이트

3. **비즈니스 로직 이동**
   - Service 클래스 구현
   - View는 Thin Controller로

4. **Celery 태스크 이동** (해당 시)
   - 명시적 태스크 이름 지정
   - Worker 재시작

5. **테스트 작성**
   - 단위 테스트
   - 통합 테스트
   - API 테스트

6. **Import 경로 업데이트**
   - 전역 검색 및 변경
   - Lint 체크

## 7. 체크리스트

### 7.1 완료 항목 ✅
- [x] Docker 컨테이너 접속
- [x] 5개 앱 생성
  - [x] skill
  - [x] search
  - [x] job_posting
  - [x] resume
  - [x] recommendation
- [x] 각 앱에 services.py 생성
- [x] 필요한 앱에 tasks.py 생성
- [x] 각 앱에 urls.py 생성
- [x] INSTALLED_APPS 등록
- [x] Django check 통과
- [x] agent/tools.py import 에러 수정

### 7.2 다음 Phase 준비사항
- [x] 앱 의존성 그래프 작성
- [x] 마이그레이션 순서 결정
- [x] 각 앱별 책임 정의
- [x] Service Layer 패턴 정의

## 8. 주의사항

### 8.1 agent 앱 Deprecated
- `agent.tools`가 `job.signals` 참조 중
- 임시로 Celery 태스크 호출로 변경
- Phase 2 완료 후 agent 앱 완전 제거 예정

### 8.2 job 앱 유지
- Phase 2 완료까지 `job` 앱 유지
- 점진적 마이그레이션으로 안전성 확보
- 각 단계마다 회귀 테스트 실행

### 8.3 URL 중복 방지
- 기존 `/api/v1/` 엔드포인트 유지
- 새 앱으로 이동 시 URL 변경 없이 라우팅만 변경
- deprecated 경고 추가 (필요 시)

---

## 📌 결론

**Phase 1.3 완료**: ✅
- 5개의 새로운 Django 앱 생성 완료
- Service Layer 템플릿 준비 완료
- INSTALLED_APPS 등록 및 Django check 통과
- Phase 2 점진적 마이그레이션 준비 완료

**다음 단계**: Phase 1.4 추가 분석 및 Phase 1.5 백업 준비

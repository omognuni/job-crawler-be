# Job Crawler Backend 리팩토링 계획

## 📋 목표
- `job` app의 과도한 책임을 도메인별로 분리
- 유지보수성과 확장성 향상
- deprecated된 `agent` app 정리
- Service Layer 패턴 도입

---

## 🐳 개발 환경 필수 사항

**⚠️ 중요: 모든 명령어는 반드시 아래 환경에서 실행해야 합니다**

### Docker 컨테이너 내부에서 실행
```bash
# Docker 컨테이너 접속
docker exec -it <container_name> bash

# 또는 docker-compose 사용 시
docker-compose exec web bash
```

### uv 가상환경 활성화
```bash
# uv 가상환경 활성화
source .venv/bin/activate

# 또는 uv run 사용
uv run python manage.py <command>
```

### 명령어 실행 예시
```bash
# 잘못된 방법 ❌
python manage.py migrate

# 올바른 방법 ✅
docker exec -it <container_name> bash
source .venv/bin/activate
python manage.py migrate

# 또는 한 줄로
docker exec -it <container_name> bash -c "source .venv/bin/activate && python manage.py migrate"

# 또는 uv run 사용
docker exec -it <container_name> uv run python manage.py migrate
```

**모든 Django 명령어, 테스트, Celery 작업은 이 환경에서 실행되어야 합니다.**

---

## 🎯 Phase 1: 준비 및 분석 (1-2주)

### 1.1 현재 코드 분석
- [ ] `job/models.py` 전체 모델 파악
- [ ] `job/views.py` 엔드포인트 및 비즈니스 로직 분석
- [ ] `job/tasks.py` Celery 작업 의존성 파악
- [ ] `job/serializers.py` 시리얼라이저 의존성 분석
- [ ] 모델 간 관계도 작성

### 1.2 테스트 환경 구축
- [ ] 기존 테스트 코드 실행 및 통과 확인
- [ ] 테스트 커버리지 측정
- [ ] 리팩토링 기준 테스트 스위트 확립

### 1.3 새로운 앱 구조 생성
- [ ] `app/job_posting/` 앱 생성 (채용 공고)
- [ ] `app/resume/` 앱 생성 (이력서)
- [ ] `app/recommendation/` 앱 생성 (추천 시스템)
- [ ] `app/skill/` 앱 생성 (스킬 추출 및 관리)
- [ ] `app/search/` 앱 생성 (검색 기능)
- [ ] 각 앱의 기본 구조 생성 (models.py, views.py, serializers.py, services.py, tasks.py, urls.py)

### 1.4 추가 분석 항목
- [ ] `job/permissions.py` 분석 및 이동 계획 수립
- [ ] `job/recommender.py` 의존성 파악 (recommendation app으로 이동 예정)
- [ ] 데이터베이스 스키마 현황 파악 (테이블, 인덱스, 제약조건)
- [ ] 외부 서비스 버전 확인 (Neo4j, ChromaDB, Redis)

### 1.5 백업 및 복구 준비
- [ ] 프로덕션 데이터베이스 백업 (pg_dump)
- [ ] Neo4j 데이터 백업 (neo4j-admin backup)
- [ ] ChromaDB 컬렉션 백업
- [ ] 백업 복원 테스트 수행
- [ ] 백업 스크립트 작성 및 문서화

---

## 💾 데이터베이스 마이그레이션 전략

### 모델 이동 시 마이그레이션 처리

**기본 원칙:**
1. 새 앱에서 기존 모델과 동일한 구조로 생성
2. `Meta.db_table`로 기존 테이블명 유지 (데이터 손실 방지)
3. `makemigrations`로 마이그레이션 파일 생성
4. 기존 앱에서 모델 제거하고 마이그레이션 생성
5. 순차적으로 `migrate` 실행하여 테이블 재할당

### 예시: JobPosting 모델 이동

```bash
# 1단계: 새 앱에 모델 생성 (기존 테이블명 유지)
# job_posting/models.py
class JobPosting(models.Model):
    # ... 필드 정의 ...
    class Meta:
        db_table = 'agent_job_posting'  # 기존 테이블명 유지!

# 2단계: 새 앱 마이그레이션 생성
uv run python manage.py makemigrations job_posting

# 3단계: fake 마이그레이션 (테이블은 이미 존재하므로)
uv run python manage.py migrate --fake job_posting

# 4단계: 기존 앱에서 모델 제거
# job/models.py에서 JobPosting 클래스 삭제

# 5단계: 기존 앱 마이그레이션 생성
uv run python manage.py makemigrations job

# 6단계: 기존 앱 마이그레이션 적용
uv run python manage.py migrate job
```

### 데이터 무결성 검증

각 마이그레이션 후 반드시 검증:

```bash
# Row count 확인
uv run python manage.py shell
>>> from job_posting.models import JobPosting
>>> JobPosting.objects.count()

# Foreign Key 관계 검증
>>> from recommendation.models import JobRecommendation
>>> JobRecommendation.objects.select_related('job_posting').count()

# 필수 필드 NOT NULL 확인
uv run python manage.py dbshell
SELECT column_name, is_nullable FROM information_schema.columns
WHERE table_name = 'agent_job_posting';
```

### 마이그레이션 체크리스트

- [ ] 마이그레이션 전 데이터베이스 백업 완료
- [ ] 테이블 row count 기록
- [ ] Foreign Key 관계 문서화
- [ ] 마이그레이션 실행 (스테이징 환경)
- [ ] 데이터 무결성 검증
- [ ] 롤백 테스트 수행
- [ ] 프로덕션 환경 적용

---

## 🔄 롤백 전략

### Phase별 롤백 체크포인트

각 주요 단계 완료 시점에 체크포인트 생성:

```bash
# Git tag 생성
git tag -a v1.0-phase1-complete -m "Phase 1: 준비 및 분석 완료"
git tag -a v1.0-phase2.1-complete -m "Phase 2.1: skill app 분리 완료"
git push origin --tags

# Docker 이미지 태깅
docker tag job-crawler-be:latest job-crawler-be:v1.0-phase1-complete
docker push job-crawler-be:v1.0-phase1-complete

# 데이터베이스 백업
pg_dump -h localhost -U postgres job_crawler_db > backup_phase1_complete.sql
```

### 롤백 절차

**문제 발생 시 즉시 롤백:**

```bash
# 1. Git 이전 체크포인트로 복원
git checkout tags/v1.0-phase1-complete -b rollback-branch

# 2. Docker 컨테이너 재시작
docker-compose down
docker-compose up --build -d

# 3. 데이터베이스 복원 (필요 시)
psql -h localhost -U postgres job_crawler_db < backup_phase1_complete.sql

# 4. 마이그레이션 상태 확인 및 조정
uv run python manage.py showmigrations
uv run python manage.py migrate <app_name> <migration_name>

# 5. Celery worker 재시작
docker-compose restart celery-worker

# 6. 서비스 정상 작동 확인
curl http://localhost:8000/health
```

### 롤백 테스트

각 Phase 완료 후 롤백 시뮬레이션:

- [ ] Phase 2.1 완료 후 롤백 테스트
- [ ] Phase 2.2 완료 후 롤백 테스트
- [ ] Phase 2.3 완료 후 롤백 테스트
- [ ] 데이터 손실 없는지 확인
- [ ] API 엔드포인트 정상 작동 확인
- [ ] Celery 작업 실행 확인

---

## 🌿 Git 워크플로우 및 브랜치 전략

### 브랜치 구조

```
main (프로덕션)
  └── develop (개발 통합)
        ├── feature/refactor-phase1-preparation
        ├── feature/refactor-skill-app
        ├── feature/refactor-search-app
        ├── feature/refactor-job-posting-app
        ├── feature/refactor-resume-app
        └── feature/refactor-recommendation-app
```

### 브랜치 명명 규칙

- `feature/refactor-<app-name>`: 앱 분리 작업
- `feature/service-layer-<app-name>`: Service Layer 도입
- `fix/<issue-description>`: 버그 수정
- `docs/<documentation-update>`: 문서 업데이트

### 커밋 컨벤션

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type:**
- `feat`: 새로운 기능 추가
- `refactor`: 코드 리팩토링 (기능 변경 없음)
- `test`: 테스트 코드 추가/수정
- `docs`: 문서 업데이트
- `chore`: 설정 파일, 빌드 스크립트 변경
- `fix`: 버그 수정

**예시:**
```bash
git commit -m "refactor(skill): skill_extractor.py를 skill app으로 이동

- job/skill_extractor.py → skill/services.py로 이동
- SkillExtractor 클래스를 SkillExtractionService로 리네임
- 모든 import 경로 업데이트
- 단위 테스트 추가

Closes #123"
```

### Pull Request 전략

**PR 템플릿:**

```markdown
## 변경 사항
-

## 체크리스트
- [ ] 테스트 통과
- [ ] 코드 리뷰 완료
- [ ] 문서 업데이트
- [ ] 마이그레이션 검증 (해당 시)
- [ ] 롤백 계획 수립

## 테스트 방법
1.
2.

## 스크린샷 (해당 시)

## 관련 이슈
Closes #
```

**리뷰 규칙:**
- 최소 1명 이상 코드 리뷰 필수
- 모든 테스트 통과 후 merge
- Squash and merge 사용 (커밋 히스토리 정리)

---

## ⚠️ 리스크 관리

### 예상 리스크 및 대응 방안

#### 리스크 1: 순환 의존성 (Circular Import)

**증상:**
- 앱 분리 후 `ImportError: cannot import name 'X' from partially initialized module`
- 서버 시작 실패

**대응 방안:**
1. 의존성 주입(DI) 패턴 사용
2. Service Layer에서 지연 import 사용
3. 공통 인터페이스를 `common` app에 정의

**예방:**
```python
# Bad: 직접 import
from job_posting.models import JobPosting

# Good: 지연 import 또는 의존성 주입
def process_recommendation(job_posting_id):
    from job_posting.models import JobPosting  # 함수 내부에서 import
    job = JobPosting.objects.get(id=job_posting_id)
```

**체크리스트:**
- [ ] 의존성 그래프 사전 작성
- [ ] 앱 간 의존 관계 최소화
- [ ] 공통 코드는 `common` app에 배치

#### 리스크 2: 데이터베이스 마이그레이션 실패

**증상:**
- `migrate` 명령 실패
- 데이터 손실 또는 테이블 중복 생성

**대응 방안:**
1. 백업에서 즉시 복원
2. `--fake` 옵션으로 마이그레이션 상태 조정
3. 수동으로 SQL 실행하여 스키마 복구

**예방:**
- [ ] 스테이징 환경에서 먼저 테스트
- [ ] 마이그레이션 전 항상 백업
- [ ] `showmigrations`로 상태 확인

#### 리스크 3: Celery 작업 큐 오류

**증상:**
- 작업 이동 후 Celery 작업 실행 안됨
- `KeyError: 'job.tasks.process_job_posting_task'`

**대응 방안:**
1. Celery worker 재시작
2. `celery -A config inspect registered`로 작업 등록 확인
3. 작업 경로 업데이트

**예방:**
```python
# celery.py에 명시적으로 작업 이름 지정
app.conf.task_routes = {
    'job_posting.tasks.process_job_posting_task': {'queue': 'default'},
}

# 또는 작업 데코레이터에 이름 명시
@shared_task(name='job_posting.process_job_posting')
def process_job_posting_task(posting_id):
    pass
```

**체크리스트:**
- [ ] Celery 설정 파일 업데이트
- [ ] Worker 재시작 절차 문서화
- [ ] 작업 모니터링 설정 (Flower)

#### 리스크 4: 외부 서비스 연결 오류 (Neo4j, ChromaDB)

**증상:**
- 앱 분리 후 Neo4j 또는 ChromaDB 연결 실패
- `ConnectionError` 또는 타임아웃

**대응 방안:**
1. `common` app의 싱글톤 클라이언트 재사용
2. 연결 설정을 환경 변수로 중앙 관리
3. 연결 풀 설정 확인

**예방:**
```python
# Good: common app의 클라이언트 재사용
from common.graph_db import graph_db_client
from common.vector_db import vector_db_client

# Bad: 각 앱에서 새로운 연결 생성
client = Neo4jClient(uri=NEO4J_URI, ...)  # ❌
```

**체크리스트:**
- [ ] 모든 앱이 `common` app 클라이언트 사용
- [ ] 연결 정보를 settings.py에서 중앙 관리
- [ ] 연결 테스트 스크립트 작성

#### 리스크 5: API 엔드포인트 변경으로 인한 클라이언트 영향

**증상:**
- 프론트엔드에서 404 또는 500 에러
- 외부 서비스 연동 오류

**대응 방안:**
1. 일정 기간 구버전 엔드포인트 유지 (deprecated 경고)
2. API 버전 관리 (v1, v2)
3. 클라이언트에 사전 공지

**예방:**
```python
# 구버전 엔드포인트 유지 (deprecated)
@api_view(['GET'])
def old_recommend_view(request):
    warnings.warn("This endpoint is deprecated. Use /api/v1/recommendations/",
                  DeprecationWarning)
    return redirect('/api/v1/recommendations/')
```

**체크리스트:**
- [ ] API 변경사항 문서화
- [ ] 클라이언트 팀에 공지
- [ ] deprecated 경고 추가
- [ ] 최소 1개월간 구버전 유지

---

## 🔄 Phase 2: 점진적 마이그레이션 (2-3주)

### 2.1 `skill` app 분리 (가장 독립적)

**코드 이동:**
- [ ] `job/skill_extractor.py` → `skill/services.py`로 이동
- [ ] `SkillExtractor` 클래스를 `SkillExtractionService`로 리네임
- [ ] 스킬 관련 유틸리티 함수 이동
- [ ] `job/permissions.py` 확인 (skill 관련 권한 있는지)

**API 엔드포인트:**
- [ ] `/api/v1/related-by-skill/<skill_name>/` 엔드포인트 이동
- [ ] `skill/views.py` 생성 및 뷰 구현
- [ ] `skill/urls.py` 생성 및 URL 패턴 정의
- [ ] 메인 `urls.py`에 skill app URL 연결

**테스트:**
- [ ] `skill/tests.py` 생성
- [ ] 단위 테스트 작성 (SkillExtractionService)
- [ ] API 테스트 작성
- [ ] Docker 컨테이너에서 테스트 실행

**임포트 경로 업데이트:**
- [ ] 전역 검색: `from job.skill_extractor import`
- [ ] 전역 검색: `import job.skill_extractor`
- [ ] 모든 임포트를 `from skill.services import`로 변경
- [ ] 서버 시작 및 동작 확인

**체크포인트:**
- [ ] Git tag 생성: `v1.0-phase2.1-complete`
- [ ] 데이터베이스 백업
- [ ] 롤백 테스트 수행

### 2.2 `search` app 분리

**Service Layer 생성:**
- [ ] `search/services.py` 생성
- [ ] `SearchService` 클래스 구현
- [ ] 벡터 검색 로직 추출 및 이동

**API 엔드포인트:**
- [ ] 검색 관련 뷰 로직 추출 (`job/views.py`에서)
- [ ] `search/views.py` 생성
- [ ] `/api/v1/search/` 엔드포인트 이동
- [ ] `search/serializers.py` 생성 (필요 시)
- [ ] `search/urls.py` 생성

**테스트:**
- [ ] 검색 API 테스트 작성
- [ ] 벡터 검색 로직 단위 테스트
- [ ] 성능 테스트 (응답 시간 측정)
- [ ] 단위 테스트 작성 및 검증

**체크포인트:**
- [ ] Git tag 생성: `v1.0-phase2.2-complete`
- [ ] 데이터베이스 백업

### 2.3 `job_posting` app 분리

**모델 마이그레이션:**
- [ ] `JobPosting` 모델을 `job_posting/models.py`로 복사
- [ ] `Meta.db_table = 'agent_job_posting'` 설정 (기존 테이블명 유지)
- [ ] `uv run python manage.py makemigrations job_posting`
- [ ] `uv run python manage.py migrate --fake job_posting`
- [ ] `job/models.py`에서 JobPosting 제거
- [ ] `uv run python manage.py makemigrations job`
- [ ] `uv run python manage.py migrate job`
- [ ] 데이터 무결성 검증 (row count 확인)

**시리얼라이저 및 뷰:**
- [ ] `JobPostingSerializer` → `job_posting/serializers.py`로 이동
- [ ] `JobPostingViewSet` → `job_posting/views.py`로 이동
- [ ] CRUD 엔드포인트 테스트
- [ ] `job_posting/urls.py` 생성 및 라우팅 설정

**Service Layer:**
- [ ] `job_posting/services.py` 생성
- [ ] `JobPostingService` 클래스 구현
- [ ] Neo4j 연동 로직 캡슐화
- [ ] ChromaDB 임베딩 로직 캡슐화

**Celery 작업:**
- [ ] `process_job_posting_task` → `job_posting/tasks.py`로 이동
- [ ] `config/celery.py`에서 작업 경로 업데이트
- [ ] Celery worker 재시작
- [ ] 작업 등록 확인: `celery -A config inspect registered`
- [ ] 테스트 작업 실행 및 확인

**권한 처리:**
- [ ] `job/permissions.py`에서 JobPosting 관련 권한 확인
- [ ] 필요 시 `job_posting/permissions.py`로 이동

**임포트 경로 업데이트:**
- [ ] `from job.models import JobPosting` 전역 검색
- [ ] `from job_posting.models import JobPosting`으로 변경
- [ ] 모든 파일에서 임포트 업데이트

**테스트:**
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 (API + DB + Celery)
- [ ] 마이그레이션 롤백 테스트

**체크포인트:**
- [ ] Git tag 생성: `v1.0-phase2.3-complete`
- [ ] 데이터베이스 백업

### 2.4 `resume` app 분리

**모델 마이그레이션:**
- [ ] `Resume` 모델을 `resume/models.py`로 복사
- [ ] `Meta.db_table` 설정으로 기존 테이블명 유지
- [ ] `uv run python manage.py makemigrations resume`
- [ ] `uv run python manage.py migrate --fake resume`
- [ ] `job/models.py`에서 Resume 제거
- [ ] `uv run python manage.py makemigrations job`
- [ ] `uv run python manage.py migrate job`
- [ ] 데이터 무결성 검증

**시리얼라이저 및 뷰:**
- [ ] `ResumeSerializer` → `resume/serializers.py`로 이동
- [ ] `ResumeViewSet` → `resume/views.py`로 이동
- [ ] CRUD 엔드포인트 이동 및 테스트
- [ ] `resume/urls.py` 생성

**Service Layer:**
- [ ] `resume/services.py` 생성
- [ ] `ResumeService` 클래스 구현
- [ ] 이력서 분석 로직 캡슐화
- [ ] LLM 기반 분석 로직 이동

**Celery 작업:**
- [ ] `process_resume_task` → `resume/tasks.py`로 이동
- [ ] Celery 설정 업데이트
- [ ] Worker 재시작 및 작업 확인

**권한 처리:**
- [ ] `job/permissions.py`에서 Resume 관련 권한 확인
- [ ] 필요 시 `resume/permissions.py`로 이동

**임포트 경로 업데이트:**
- [ ] `from job.models import Resume` 전역 검색 및 변경
- [ ] 모든 임포트 경로 업데이트

**테스트:**
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 작성
- [ ] 이력서 분석 로직 테스트

**체크포인트:**
- [ ] Git tag 생성: `v1.0-phase2.4-complete`
- [ ] 데이터베이스 백업

### 2.5 `recommendation` app 분리

**모델 마이그레이션:**
- [ ] `JobRecommendation` 모델을 `recommendation/models.py`로 복사
- [ ] `Meta.db_table` 설정으로 기존 테이블명 유지
- [ ] 마이그레이션 생성 및 적용
- [ ] `job/models.py`에서 JobRecommendation 제거
- [ ] 데이터 무결성 검증

**시리얼라이저 및 뷰:**
- [ ] `JobRecommendationSerializer` → `recommendation/serializers.py`로 이동
- [ ] `JobRecommendationViewSet` → `recommendation/views.py`로 이동
- [ ] `recommendation/urls.py` 생성

**추천 엔진:**
- [ ] `job/recommender.py` → `recommendation/services.py`로 이동
- [ ] `get_recommendations` 함수를 `RecommendationService` 클래스로 리팩토링
- [ ] 하이브리드 추천 로직 캡슐화 (Vector + Graph)

**엔드포인트 통합 (중복 제거):**
- [ ] `/api/v1/recommendations/for-user/<user_id>/` 유지
- [ ] `/api/v1/recommend/` deprecated 경고 추가
- [ ] 일정 기간 후 `/api/v1/recommend/` 제거 계획 수립
- [ ] API 문서 업데이트

**권한 처리:**
- [ ] `job/permissions.py`에서 Recommendation 관련 권한 확인
- [ ] 필요 시 `recommendation/permissions.py`로 이동

**임포트 경로 업데이트:**
- [ ] `from job.models import JobRecommendation` 전역 검색
- [ ] `from job.recommender import` 전역 검색
- [ ] 모든 임포트 경로 업데이트

**테스트:**
- [ ] 단위 테스트 작성 (RecommendationService)
- [ ] 통합 테스트 (추천 API 전체 플로우)
- [ ] 성능 테스트 (응답 시간 < 500ms)

**체크포인트:**
- [ ] Git tag 생성: `v1.0-phase2.5-complete`
- [ ] 데이터베이스 백업
- [ ] Phase 2 완료 회고

---

## 🏗️ Phase 3: Service Layer 패턴 도입 (1-2주)

### 3.1 각 앱에 Service Layer 구현
```
job_posting/
├── models.py
├── views.py          # API 인터페이스만 (thin controller)
├── serializers.py
├── services.py       # 비즈니스 로직
├── tasks.py          # Celery 작업
└── urls.py

resume/
├── models.py
├── views.py
├── serializers.py
├── services.py       # 이력서 분석 로직
├── tasks.py
└── urls.py

recommendation/
├── models.py
├── views.py
├── serializers.py
├── services.py       # 추천 엔진 로직
└── urls.py

skill/
├── services.py       # 스킬 추출 로직
├── views.py
└── urls.py

search/
├── services.py       # 검색 로직
├── views.py
└── urls.py
```

### 3.2 Service 클래스 설계
- [ ] `JobPostingService`: 채용 공고 생성/수정/삭제 로직
- [ ] `ResumeService`: 이력서 분석 및 처리 로직
- [ ] `RecommendationService`: 하이브리드 추천 엔진
- [ ] `SkillExtractionService`: 스킬 추출 로직
- [ ] `SearchService`: 벡터/하이브리드 검색 로직

### 3.3 View를 Thin Controller로 리팩토링
- [ ] 비즈니스 로직을 Service로 위임
- [ ] View는 요청/응답 처리만 담당
- [ ] 예외 처리 및 로깅 추가

---

## 🧹 Phase 4: 정리 및 최적화 (1주)

### 4.1 기존 코드 정리
- [ ] `job/` app의 빈 파일 확인 및 제거
- [ ] `job/` app 제거 (모든 기능 이전 완료 후)
- [ ] 사용되지 않는 import 정리
- [ ] 코드 포맷팅 (black, isort)

### 4.2 `agent` app 처리
- [ ] agent app 사용 여부 최종 확인
- [ ] 옵션 A: 완전 제거
- [ ] 옵션 B: `ai_experiments/`로 이름 변경 및 격리

### 4.3 URL 라우팅 재구성
```python
# config/urls.py
urlpatterns = [
    path('api/v1/jobs/', include('job_posting.urls')),
    path('api/v1/resumes/', include('resume.urls')),
    path('api/v1/recommendations/', include('recommendation.urls')),
    path('api/v1/skills/', include('skill.urls')),
    path('api/v1/search/', include('search.urls')),
]
```
- [ ] 중복 엔드포인트 제거
- [ ] RESTful 원칙에 맞게 URL 정리
- [ ] API 버전 관리 전략 수립

### 4.4 설정 파일 정리
- [ ] `settings/base.py`, `development.py`, `production.py` 분리
- [ ] `INSTALLED_APPS`에 새로운 앱 등록
- [ ] 환경 변수 관리 개선 (.env 활용)

### 4.5 의존성 정리

**패키지 정리:**
- [ ] `pyproject.toml`에서 사용하지 않는 패키지 확인
- [ ] deprecated된 패키지 제거
- [ ] 패키지 버전 업데이트 (보안 패치)

**의존성 재생성:**
```bash
# 사용하지 않는 패키지 확인
uv run pip list --not-required

# uv lock 재생성
uv lock

# 의존성 동기화
uv sync
```

**Docker 이미지 최적화:**
- [ ] Docker 이미지 빌드
- [ ] 이미지 크기 확인 및 최적화
- [ ] 레이어 캐싱 최적화
- [ ] Multi-stage build 적용 (필요 시)

**보안 점검:**
- [ ] 보안 취약점 스캔: `uv pip check`
- [ ] 알려진 CVE 확인
- [ ] 취약한 패키지 업데이트

**체크리스트:**
```bash
# 현재 이미지 크기 확인
docker images | grep job-crawler-be

# 빌드 및 크기 비교
docker-compose build
docker images | grep job-crawler-be

# 컨테이너 실행 및 테스트
docker-compose up -d
docker-compose exec web uv run python manage.py check
```

---

## 🧪 Phase 5: 테스트 및 검증 (1주)

### 5.1 테스트 커버리지
- [ ] 각 Service 단위 테스트 (목표: 80% 이상)
- [ ] API 통합 테스트
- [ ] Celery 작업 테스트
- [ ] E2E 테스트 (주요 시나리오)

### 5.2 성능 테스트 메트릭

**응답 시간 목표:**
- [ ] 추천 시스템 응답 시간: 목표 < 500ms (p95)
- [ ] 검색 API 응답 시간: 목표 < 300ms (p95)
- [ ] 채용 공고 CRUD API: 목표 < 200ms (p95)
- [ ] 이력서 CRUD API: 목표 < 200ms (p95)

**데이터베이스 쿼리 최적화:**
- [ ] N+1 문제 확인 및 제거 (`select_related`, `prefetch_related` 사용)
- [ ] 느린 쿼리 로깅 활성화 (> 100ms)
- [ ] 인덱스 최적화 (자주 검색되는 필드)
- [ ] 쿼리 실행 계획 분석 (`EXPLAIN`)

**Celery 작업 처리 시간:**
- [ ] Job Posting 처리: 목표 < 5초
- [ ] Resume 분석 처리: 목표 < 10초
- [ ] 작업 실패율: 목표 < 1%
- [ ] 재시도 메커니즘 검증

**리소스 사용량:**
- [ ] 메모리 사용량: 컨테이너당 < 512MB
- [ ] CPU 사용률: 평균 < 50%
- [ ] DB 연결 수: < 50개
- [ ] Redis 메모리 사용량 확인

**성능 테스트 도구:**
```bash
# API 부하 테스트 (locust 또는 ab)
uv run locust -f tests/locustfile.py --host=http://localhost:8000

# Django 쿼리 분석
uv run python manage.py debugsqlshell

# 프로파일링
uv run python -m cProfile -o profile.stats manage.py runserver
```

**비교 측정:**
- [ ] 리팩토링 전 성능 기준선 측정
- [ ] 리팩토링 후 성능 측정
- [ ] 성능 개선율 계산 및 문서화
- [ ] 성능 저하 발견 시 원인 분석 및 개선

### 5.3 문서화
- [ ] 각 앱의 README.md 작성
- [ ] API 문서 업데이트 (Swagger/OpenAPI)
- [ ] 아키텍처 다이어그램 작성
- [ ] 마이그레이션 가이드 작성
- [ ] 성능 테스트 결과 문서화
- [ ] 롤백 절차 문서화

### 5.4 보안 체크리스트

**인증 및 권한:**
- [ ] 모든 API 엔드포인트 인증 확인
- [ ] 권한 체크 (IsAuthenticated, IsOwner 등)
- [ ] JWT 토큰 만료 시간 검증
- [ ] 사용자별 접근 권한 테스트

**입력 검증:**
- [ ] SQL Injection 취약점 검사
- [ ] XSS (Cross-Site Scripting) 방어 확인
- [ ] CSRF 토큰 검증
- [ ] 파일 업로드 검증 (타입, 크기)
- [ ] URL 파라미터 검증

**민감 정보 보호:**
- [ ] 환경 변수 노출 확인 (`.env` 파일 `.gitignore` 등록)
- [ ] API 키, 비밀번호 하드코딩 확인
- [ ] 민감한 정보 로깅 방지
- [ ] 에러 메시지에서 민감 정보 노출 방지

**HTTPS 및 통신 보안:**
- [ ] HTTPS 강제 (프로덕션)
- [ ] CORS 설정 검증
- [ ] Content Security Policy (CSP) 헤더
- [ ] Security 헤더 설정 (X-Frame-Options, X-Content-Type-Options)

**의존성 보안:**
- [ ] 알려진 보안 취약점 스캔
- [ ] 오래된 패키지 업데이트
- [ ] `uv pip check` 실행
- [ ] Dependabot 또는 Snyk 설정

**데이터베이스 보안:**
- [ ] DB 접근 권한 최소화 (Principle of Least Privilege)
- [ ] 데이터베이스 연결 암호화
- [ ] 백업 데이터 암호화
- [ ] SQL 인젝션 방어 (ORM 사용 확인)

**보안 테스트:**
```bash
# OWASP ZAP 스캔 (선택)
docker run -t owasp/zap2docker-stable zap-baseline.py -t http://localhost:8000

# Django 보안 체크
uv run python manage.py check --deploy

# 민감 정보 검색
grep -r "password\|secret\|api_key" --exclude-dir=venv --exclude-dir=.git
```

**체크리스트:**
- [ ] 보안 감사 수행
- [ ] 침투 테스트 (선택)
- [ ] 보안 정책 문서화
- [ ] 팀원 보안 교육

---

## 📊 Phase 6: 배포 및 모니터링 (1주)

### 6.1 스테이징 배포
- [ ] 스테이징 환경에 배포
- [ ] QA 테스트 수행
- [ ] 버그 수정 및 안정화

### 6.2 프로덕션 배포
- [ ] Blue-Green 배포 또는 Canary 배포 전략 수립
- [ ] 롤백 계획 준비
- [ ] 프로덕션 배포

### 6.3 모니터링
- [ ] 로그 모니터링 설정
- [ ] 성능 메트릭 수집
- [ ] 에러 트래킹 (Sentry 등)
- [ ] 2주간 모니터링 및 핫픽스

---

## 🎁 추가 개선 사항 (선택)

### 의존성 역전 원칙 (DIP) 적용
- [ ] `IVectorSearchService` 인터페이스 정의
- [ ] `IGraphDBService` 인터페이스 정의
- [ ] 구현체를 쉽게 교체할 수 있도록 설계

### 캐싱 전략
- [ ] Redis 캐싱 도입 (추천 결과, 검색 결과)
- [ ] 캐시 무효화 전략 수립

### 비동기 처리 개선
- [ ] Celery 작업 우선순위 설정
- [ ] 작업 재시도 로직 개선
- [ ] 작업 모니터링 대시보드 (Flower)

---

## ⏱️ 전체 타임라인

| Phase | 기간 | 상태 |
|-------|------|------|
| Phase 1: 준비 및 분석 | 1-2주 | ⬜️ 대기 |
| Phase 2: 점진적 마이그레이션 | 2-3주 | ⬜️ 대기 |
| Phase 3: Service Layer 도입 | 1-2주 | ⬜️ 대기 |
| Phase 4: 정리 및 최적화 | 1주 | ⬜️ 대기 |
| Phase 5: 테스트 및 검증 | 1주 | ⬜️ 대기 |
| Phase 6: 배포 및 모니터링 | 1주 | ⬜️ 대기 |
| **전체** | **7-10주** | ⬜️ 대기 |

---

## 📚 명령어 실행 가이드

### Django 앱 생성

```bash
# Docker 컨테이너 접속
docker exec -it <container_name> bash

# uv 가상환경 활성화
source .venv/bin/activate

# app 디렉토리로 이동
cd app

# 새로운 앱 생성
python manage.py startapp job_posting
python manage.py startapp resume
python manage.py startapp recommendation
python manage.py startapp skill
python manage.py startapp search

# settings.py에 앱 등록 확인
# INSTALLED_APPS에 추가:
#   'job_posting',
#   'resume',
#   'recommendation',
#   'skill',
#   'search',
```

### 마이그레이션 실행

```bash
# 마이그레이션 파일 생성
uv run python manage.py makemigrations job_posting

# 생성된 마이그레이션 확인
uv run python manage.py showmigrations job_posting

# 마이그레이션 적용
uv run python manage.py migrate job_posting

# fake 마이그레이션 (테이블이 이미 존재하는 경우)
uv run python manage.py migrate --fake job_posting 0001

# 전체 마이그레이션 상태 확인
uv run python manage.py showmigrations

# 마이그레이션 롤백
uv run python manage.py migrate job_posting 0001  # 특정 마이그레이션으로 롤백
uv run python manage.py migrate job_posting zero  # 모든 마이그레이션 롤백
```

### 데이터베이스 작업

```bash
# Django shell 접속
uv run python manage.py shell

# 데이터 검증 (shell 내부)
>>> from job_posting.models import JobPosting
>>> JobPosting.objects.count()
>>> JobPosting.objects.first()

# 데이터베이스 백업
docker exec <postgres_container> pg_dump -U postgres job_crawler_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 데이터베이스 복원
docker exec -i <postgres_container> psql -U postgres job_crawler_db < backup_20241120_120000.sql

# 데이터베이스 직접 접속
uv run python manage.py dbshell
```

### 테스트 실행

```bash
# 전체 테스트 실행
uv run pytest

# 특정 앱 테스트
uv run pytest app/job_posting/tests.py

# 특정 테스트 클래스/함수
uv run pytest app/job_posting/tests.py::TestJobPostingService
uv run pytest app/job_posting/tests.py::TestJobPostingService::test_create_job_posting

# 커버리지 측정
uv run pytest --cov=app --cov-report=html
uv run pytest --cov=app --cov-report=term-missing

# 커버리지 결과 확인 (브라우저)
# htmlcov/index.html 파일 열기

# 병렬 테스트 실행 (성능 향상)
uv run pytest -n auto

# 특정 마커만 실행
uv run pytest -m "not slow"
```

### Celery 작업 관리

```bash
# Celery worker 시작 (포그라운드)
celery -A config worker -l info

# Celery worker 백그라운드 실행
celery -A config worker -l info --detach

# 작업 등록 확인
celery -A config inspect registered

# 활성 작업 확인
celery -A config inspect active

# 작업 통계
celery -A config inspect stats

# 특정 작업 실행 (테스트)
uv run python manage.py shell
>>> from job_posting.tasks import process_job_posting_task
>>> process_job_posting_task.delay(posting_id=1)

# Flower 모니터링 시작
celery -A config flower --port=5555
# 브라우저에서 http://localhost:5555 접속

# Worker 재시작 (코드 변경 후)
docker-compose restart celery-worker
```

### 코드 품질 검사

```bash
# Django 체크
uv run python manage.py check
uv run python manage.py check --deploy  # 프로덕션 설정 체크

# 코드 포맷팅 (black)
uv run black app/

# Import 정리 (isort)
uv run isort app/

# Linting (flake8)
uv run flake8 app/

# Type 체크 (mypy, 선택)
uv run mypy app/

# 전체 품질 검사 스크립트
uv run black app/ && uv run isort app/ && uv run flake8 app/ && uv run pytest
```

### Docker 관리

```bash
# 컨테이너 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f web
docker-compose logs -f celery-worker
docker-compose logs --tail=100 web

# 컨테이너 재시작
docker-compose restart web
docker-compose restart celery-worker

# 이미지 재빌드
docker-compose build
docker-compose up --build -d

# 전체 재시작 (클린)
docker-compose down
docker-compose up -d

# 볼륨 포함 완전 제거 (주의!)
docker-compose down -v
```

### 임포트 경로 변경

```bash
# 전역 검색 및 변경 (VSCode)
# Ctrl+Shift+H (또는 Cmd+Shift+H)
# 검색: from job.models import JobPosting
# 변경: from job_posting.models import JobPosting

# grep으로 확인
grep -r "from job.models import JobPosting" app/
grep -r "from job.skill_extractor" app/

# sed로 일괄 변경 (리눅스/맥)
find app/ -type f -name "*.py" -exec sed -i 's/from job.models import JobPosting/from job_posting.models import JobPosting/g' {} +

# Python 스크립트로 변경 (더 안전)
# scripts/update_imports.py 생성 후 실행
uv run python scripts/update_imports.py
```

### 성능 프로파일링

```bash
# Django Debug Toolbar 활성화 (개발 환경)
# settings.py에서 DEBUG=True 확인

# 쿼리 분석
uv run python manage.py shell
>>> from django.db import connection
>>> from django.test.utils import override_settings
>>> with override_settings(DEBUG=True):
...     # 쿼리 실행
...     print(len(connection.queries))
...     print(connection.queries)

# cProfile 사용
uv run python -m cProfile -o profile.stats manage.py test

# profile.stats 분석
uv run python -m pstats profile.stats
```

---

## 📝 주의사항

1. **🐳 개발 환경 필수**: 모든 명령어는 반드시 Docker 컨테이너 내부의 uv 가상환경에서 실행
2. **💾 백업 필수**: 각 Phase 시작 전 반드시 데이터베이스, Neo4j, ChromaDB 백업 수행
3. **점진적 접근**: 한 번에 모든 것을 변경하지 말고 단계별로 진행
4. **테스트 우선**: 각 단계마다 테스트 작성 및 검증
5. **롤백 준비**: 각 Phase 완료 시 Git tag 생성 및 롤백 테스트 수행
6. **백워드 호환성**: 기존 API 사용자를 위한 호환성 유지 (필요시 deprecated 경고)
7. **문서화**: 변경사항을 즉시 문서화
8. **코드 리뷰**: 각 단계마다 팀원과 코드 리뷰 수행
9. **보안 검증**: 민감 정보 노출, 권한 체크, 입력 검증 확인
10. **성능 모니터링**: 리팩토링 전/후 성능 비교 및 저하 방지

### 백업 체크리스트

**Phase 시작 전 필수 백업:**

```bash
# 1. PostgreSQL 백업
docker exec <postgres_container> pg_dump -U postgres job_crawler_db > \
  backup/db_$(date +%Y%m%d_%H%M%S).sql

# 2. Neo4j 백업
docker exec <neo4j_container> neo4j-admin backup \
  --backup-dir=/var/lib/neo4j/backup --name=graph_$(date +%Y%m%d_%H%M%S)

# 3. ChromaDB 백업 (디렉토리 복사)
docker exec <chroma_container> tar -czf \
  /backup/chroma_$(date +%Y%m%d_%H%M%S).tar.gz /chroma/data

# 4. 코드 백업 (Git tag)
git tag -a backup-phase1-$(date +%Y%m%d) -m "Backup before Phase 1"
git push origin --tags

# 5. 백업 확인
ls -lh backup/
```

**백업 보관 정책:**
- 최소 3개 이상의 백업 유지
- 각 Phase 완료 시점 백업 별도 보관
- 프로덕션 배포 전 최종 백업 필수
- 백업 파일은 안전한 외부 스토리지에도 보관 (S3, NAS 등)

---

## 🚀 시작하기

리팩토링을 시작하려면:
1. **개발 환경 확인**: Docker 컨테이너가 실행 중이고 uv 가상환경이 활성화되었는지 확인
2. 이 계획서를 팀과 공유하고 피드백 받기
3. Phase 1.1부터 체크리스트를 하나씩 완료
4. 각 Phase 완료 후 회고 및 다음 Phase 조정

```bash
# 개발 환경 확인 방법
docker ps  # 컨테이너 실행 확인
docker exec -it <container_name> bash
source .venv/bin/activate  # 또는 uv run 사용
python --version  # Python 버전 확인
```

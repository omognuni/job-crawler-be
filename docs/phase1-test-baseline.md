# Phase 1.2: 테스트 환경 구축 및 기준선 확립 결과

## 📊 측정 일자
2025년 11월 20일

## 1. 테스트 실행 결과

### 1.1 전체 테스트 통계
- **총 테스트**: 10개
- **통과**: 8개 (80%)
- **실패**: 2개 (20%)

### 1.2 실패한 테스트
1. `test_job_posting_schedules_celery_task_on_save`
   - **원인**: Celery 태스크 모킹 문제
   - **상태**: 트랜잭션 커밋 후 태스크 호출로 인해 모킹이 어려움
   - **해결 방안**: 통합 테스트로 변경 또는 트랜잭션 처리 개선

2. `test_related_jobs_view`
   - **원인**: Import 경로 문제 (`module 'job' has no attribute 'views'`)
   - **상태**: 패키지 구조 문제
   - **해결 방안**: Import 경로 수정 필요

## 2. 코드 커버리지 분석

### 2.1 전체 커버리지
- **전체 커버리지**: 38%
- **총 라인 수**: 547줄
- **테스트된 라인**: 207줄
- **미테스트 라인**: 340줄

### 2.2 파일별 커버리지

| 파일 | 커버리지 | 상태 | 우선순위 |
|------|----------|------|----------|
| `models.py` | 78% | 🟡 양호 | Medium |
| `skill_extractor.py` | 81% | 🟢 좋음 | Low |
| `tests.py` | 88% | 🟢 좋음 | - |
| `admin.py` | 100% | 🟢 완벽 | - |
| `apps.py` | 100% | 🟢 완벽 | - |
| `migrations/*` | 100% | 🟢 완벽 | - |
| **`tasks.py`** | **10%** | 🔴 **매우 낮음** | **High** |
| **`recommender.py`** | **0%** | 🔴 **없음** | **Critical** |
| **`views.py`** | **5%** | 🔴 **매우 낮음** | **High** |
| `serializers.py` | 0% | 🔴 없음 | Medium |
| `permissions.py` | 0% | 🔴 없음 | Low |
| `urls.py` | 0% | 🔴 없음 | Low |

### 2.3 미테스트 코드 분석

#### Critical: 추천 엔진 (`recommender.py`) - 0% 커버리지
**누락된 테스트**:
- `get_recommendations()`: 핵심 비즈니스 로직
- `_filter_by_skill_graph()`: Neo4j 스킬 매칭
- `_calculate_match_score_and_reason()`: 점수 계산
- `get_skill_statistics()`: 스킬 통계

**영향도**: 🔴 **매우 높음** (핵심 비즈니스 로직)

#### High: Celery 태스크 (`tasks.py`) - 10% 커버리지
**누락된 테스트**:
- `process_job_posting()`: 채용공고 처리 워크플로우
  - 스킬 추출
  - ChromaDB 임베딩
  - Neo4j 관계 생성
  - 재시도 로직
- `process_resume()`: 이력서 처리 워크플로우
  - LLM 호출 (Gemini)
  - 경력 분석
  - ChromaDB 임베딩
  - Fallback 로직

**영향도**: 🔴 **매우 높음** (비동기 처리 로직)

#### High: API 뷰 (`views.py`) - 5% 커버리지
**누락된 테스트**:
- `JobPostingViewSet`: CRUD 작업
- `ResumeViewSet`: CRUD 작업
- `JobRecommendationViewSet`: CRUD + 실시간 추천
- `JobSearchView`: 벡터 검색
- `RecommendationsView`: 중복 추천 엔드포인트

**영향도**: 🟡 **높음** (API 엔드포인트)

## 3. 테스트 작성 우선순위

### Phase 1.2 완료 후 추가 작업 (선택)

**우선순위 1: 추천 엔진 테스트 (Critical)**
```python
# test_recommender.py (신규 작성 필요)
- test_get_recommendations_success
- test_get_recommendations_no_resume
- test_filter_by_skill_graph
- test_calculate_match_score_required_skills
- test_calculate_match_score_preferred_skills
- test_calculate_match_score_career_range
```

**우선순위 2: Celery 태스크 테스트 (High)**
```python
# test_tasks.py (신규 작성 필요)
- test_process_job_posting_success
- test_process_job_posting_not_found
- test_process_job_posting_retry
- test_process_resume_success
- test_process_resume_no_analysis_needed
- test_process_resume_llm_fallback
```

**우선순위 3: ViewSet 테스트 (High)**
```python
# test_views.py (신규 작성 필요)
- test_job_posting_viewset_list
- test_job_posting_viewset_create
- test_resume_viewset_crud
- test_job_recommendation_viewset_for_user
```

## 4. 테스트 환경 설정

### 4.1 설치된 패키지
- `pytest==8.4.2`
- `pytest-django==4.11.1`
- `pytest-mock==3.15.1`
- `pytest-cov==7.0.0` (새로 설치)
- `pytest-celery==1.2.1`

### 4.2 테스트 실행 명령어
```bash
# Docker 컨테이너 내부에서 실행
docker exec app bash -c "uv run pytest job/tests.py -v"

# 커버리지 측정
docker exec app bash -c "uv run pytest job/tests.py --cov=job --cov-report=term-missing"

# HTML 리포트 생성
docker exec app bash -c "uv run pytest job/tests.py --cov=job --cov-report=html"
```

### 4.3 pytest 설정 (`pytest.ini`)
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
```

## 5. 테스트 작성 가이드라인

### 5.1 테스트 구조
```python
# 단위 테스트
class TestSkillExtractor(TestCase):
    def test_extract_skills_backend(self):
        # Given
        text = "Python, Django 경험"

        # When
        skills = extract_skills(text)

        # Then
        self.assertIn("Python", skills)
        self.assertIn("Django", skills)

# 통합 테스트
@pytest.mark.django_db
class TestJobPostingWorkflow(TestCase):
    @patch("common.vector_db.vector_db_client")
    @patch("common.graph_db.graph_db_client")
    def test_full_job_posting_workflow(self, mock_graph, mock_vector):
        # Mock 설정 및 전체 워크플로우 테스트
        pass
```

### 5.2 모킹 전략
- **외부 서비스**: Neo4j, ChromaDB, Redis → Mock 필수
- **LLM 호출**: Gemini API → Mock 필수
- **Celery 태스크**: `@patch("job.tasks.task_name.delay")` 사용
- **트랜잭션**: `@pytest.mark.django_db` 사용

### 5.3 테스트 데이터
- **Fixture 사용**: `conftest.py`에 공통 fixture 정의
- **Factory 패턴**: 복잡한 객체 생성 시 factory 함수 사용
- **테스트 DB**: 별도 테스트 데이터베이스 사용 (`test_db`)

## 6. 기준선 설정

### 6.1 리팩토링 전 기준선
- **전체 테스트**: 10개 (8개 통과)
- **커버리지**: 38%
- **핵심 로직 커버리지**:
  - `recommender.py`: 0% ❌
  - `tasks.py`: 10% ❌
  - `models.py`: 78% ✅
  - `skill_extractor.py`: 81% ✅

### 6.2 리팩토링 후 목표
- **전체 테스트**: 50개 이상
- **커버리지**: 80% 이상
- **핵심 로직 커버리지**: 90% 이상
- **CI/CD 통합**: GitHub Actions 또는 GitLab CI

### 6.3 회귀 테스트 전략
1. **기준선 테스트 스위트 확립** ✅ (완료)
2. **각 Phase 완료 후 기준선 테스트 실행**
3. **새로운 앱 분리 시 해당 앱 테스트 추가**
4. **API 계약 테스트 추가** (Swagger/OpenAPI 활용)

## 7. 테스트 자동화

### 7.1 로컬 테스트 스크립트
```bash
#!/bin/bash
# scripts/run_tests.sh
docker exec app bash -c "uv run pytest --cov=job --cov-report=html --tb=short"
echo "Coverage report: htmlcov/index.html"
```

### 7.2 CI/CD 통합 (향후)
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: docker-compose run web pytest --cov
```

## 8. 알려진 이슈

### 8.1 Celery 태스크 테스트
- **문제**: `transaction.on_commit()` 사용으로 인해 모킹 어려움
- **해결책**: 통합 테스트로 전환하거나 태스크 직접 호출 테스트

### 8.2 Import 경로
- **문제**: `module 'job' has no attribute 'views'` 에러
- **해결책**: `from job import views` → `from job.views import ...`로 변경

### 8.3 외부 서비스 의존성
- **문제**: Neo4j, ChromaDB, Redis 연결 필요
- **해결책**: Docker 컨테이너 환경에서 테스트 실행 또는 Mock 사용

## 9. 다음 단계

### Phase 1.3: 새로운 앱 구조 생성
- [ ] Docker 컨테이너 접속
- [ ] 5개 앱 생성 (skill, search, job_posting, resume, recommendation)
- [ ] INSTALLED_APPS 등록
- [ ] 기본 구조 파일 생성

### Phase 1.4: 추가 분석
- [ ] permissions.py 분석
- [ ] recommender.py 의존성 파악
- [ ] 데이터베이스 스키마 현황 파악
- [ ] 외부 서비스 버전 확인

---

## 📌 결론

**테스트 환경 구축 완료**:
- ✅ pytest 환경 설정
- ✅ 기본 테스트 작성 및 실행 (80% 통과율)
- ✅ 코드 커버리지 측정 (38% 기준선)
- ✅ 테스트 인프라 구축

**주요 발견사항**:
- 핵심 비즈니스 로직 (recommender, tasks)의 테스트 커버리지 매우 낮음
- 기존 테스트 코드가 오래된 구현 참조 (signals.py)
- Celery 태스크 테스트 전략 필요

**리팩토링 준비 상태**: ✅ **Ready**
- 기준선 테스트 스위트 확립
- 회귀 테스트 실행 가능
- 안전한 리팩토링 환경 구축 완료

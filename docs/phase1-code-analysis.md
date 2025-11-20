# Phase 1.1: 현재 코드 분석 결과

## 📊 분석 일자
2025년 11월 20일

## 1. 모델 구조 분석 (`job/models.py`)

### 1.1 JobPosting 모델
- **테이블명**: `agent_job_posting`
- **주요 필드**:
  - `posting_id`: IntegerField (PK)
  - `url`, `company_name`, `position`: 기본 정보
  - `main_tasks`, `requirements`, `preferred_points`: 공고 상세
  - `location`, `district`, `employment_type`: 위치/고용 형태
  - `career_min`, `career_max`: 경력 범위
  - `skills_required`: JSONField (필수 스킬 목록)
  - `skills_preferred`: TextField (우대사항 원문)
  - `created_at`, `updated_at`: 타임스탬프

- **비즈니스 로직**:
  - `save()` 오버라이드: 저장 후 Celery 태스크 자동 호출
  - 무한 루프 방지: `update_fields` 체크로 스킬 업데이트 시 태스크 스킵

### 1.2 Resume 모델
- **테이블명**: `agent_resume`
- **주요 필드**:
  - `user_id`: IntegerField (unique)
  - `content`: TextField (이력서 원문)
  - `content_hash`: CharField (SHA-256 해시)
  - `analysis_result`: JSONField (스킬, 경력, 강점)
  - `experience_summary`: TextField (임베딩용 요약)
  - `analyzed_at`: DateTimeField (마지막 분석 시간)

- **비즈니스 로직**:
  - `calculate_hash()`: 이력서 내용의 해시값 계산
  - `needs_analysis()`: 해시 비교로 재분석 필요 여부 판단
  - `save()` 오버라이드: 내용 변경 시에만 Celery 태스크 호출

### 1.3 JobRecommendation 모델
- **테이블명**: `agent_job_recommendation`
- **주요 필드**:
  - `user_id`: IntegerField
  - `job_posting`: ForeignKey to JobPosting
  - `rank`: IntegerField (1-10)
  - `match_score`: FloatField
  - `match_reason`: TextField
  - `created_at`: DateTimeField

- **제약 조건**: `unique_together = ["user_id", "rank", "created_at"]`
- **정렬**: `ordering = ["user_id", "rank"]`

## 2. 뷰 및 API 엔드포인트 분석 (`job/views.py`)

### 2.1 ViewSets (CRUD)
1. **JobPostingViewSet**: `/api/v1/job-postings/`
2. **ResumeViewSet**: `/api/v1/resumes/`
3. **JobRecommendationViewSet**: `/api/v1/recommendations/`
   - 커스텀 액션: `for-user/<user_id>/` - 실시간 추천 생성

### 2.2 APIView (비즈니스 로직)
1. **JobSearchView**: `/api/v1/search/`
   - 벡터 유사도 기반 검색
   - `agent.tools.vector_search_job_postings_tool` 사용 ⚠️

2. **RelatedJobsView**: `/api/v1/related-by-skill/<skill_name>/`
   - Neo4j 그래프 DB 기반 스킬 매칭
   - `graph_db_client.get_jobs_related_to_skill()` 호출

3. **RecommendationsView**: `/api/v1/recommend/`
   - 실시간 추천 생성 (중복 엔드포인트)
   - `job.recommender.get_recommendations()` 호출

### 2.3 중복 엔드포인트 발견 ⚠️
- `/api/v1/recommendations/for-user/<user_id>/` (JobRecommendationViewSet)
- `/api/v1/recommend/?user_id=<int>` (RecommendationsView)
- **결정 필요**: 하나로 통합 또는 하나를 deprecated 처리

## 3. Celery 태스크 분석 (`job/tasks.py`)

### 3.1 process_job_posting 태스크
**처리 흐름**:
1. JobPosting 조회
2. 스킬 추출 (`skill_extractor.extract_skills_from_job_posting`)
3. `skills_required`, `skills_preferred` 업데이트
4. 임베딩 텍스트 생성 (position + main_tasks + requirements + preferred_points)
5. ChromaDB 'job_postings' 컬렉션에 upsert
6. Neo4j에 (JobPosting)-[:REQUIRES_SKILL]->(Skill) 관계 생성

**의존성**:
- `common.vector_db.vector_db_client`
- `common.graph_db.graph_db_client`
- `job.skill_extractor`

**재시도**: max_retries=3, countdown=60초

### 3.2 process_resume 태스크
**처리 흐름**:
1. Resume 조회 및 `needs_analysis()` 체크
2. LLM-Free 스킬 추출 (`skill_extractor.extract_skills`)
3. LLM 호출 (Gemini 2.0 Flash) - 경력 연차, 강점, 경력 요약 추출
4. `analysis_result`, `experience_summary`, `analyzed_at` 업데이트
5. ChromaDB 'resumes' 컬렉션에 upsert

**의존성**:
- `google.genai` (Gemini API)
- `common.vector_db.vector_db_client`
- `job.skill_extractor`

**Fallback**: LLM 실패 시 정규식 기반 분석으로 대체

## 4. 시리얼라이저 분석 (`job/serializers.py`)

### 4.1 JobPostingSerializer
- 단순 ModelSerializer
- 필드: posting_id, url, company_name, position, main_tasks, requirements, preferred_points, location, district, employment_type, career_min, career_max, created_at, updated_at

### 4.2 ResumeSerializer
- `needs_analysis` SerializerMethodField 포함
- read_only_fields: content_hash, analyzed_at

### 4.3 JobRecommendationSerializer
- `job_posting` 중첩 시리얼라이저 (read_only)

## 5. 핵심 비즈니스 로직 분석

### 5.1 스킬 추출 (`job/skill_extractor.py`)
- **LLM-Free**: 정규식 패턴 매칭
- **마스터 스킬 목록**: 104개 기술 스택 (Backend, Frontend, Database, Cloud, Tools)
- **함수**:
  - `extract_skills(text)`: 텍스트에서 스킬 추출
  - `extract_skills_from_job_posting()`: 필수 스킬 + 우대사항 추출
  - `get_all_skills()`, `get_skill_count()`: 유틸리티
- **캐싱**: `@lru_cache`로 컴파일된 패턴 캐싱

### 5.2 추천 엔진 (`job/recommender.py`)
**하이브리드 추천 알고리즘**:
1. Resume에서 사용자 스킬 및 경력 추출
2. ChromaDB에서 벡터 유사도 기반 후보 50개 조회
3. Neo4j로 스킬 그래프 매칭하여 20개로 정제
4. 각 공고에 대해 match_score 계산 (0-100점):
   - 필수 스킬 매칭: 최대 50점
   - 우대사항 매칭: 최대 30점
   - 경력 범위 일치: 최대 20점
5. match_reason 생성 (한국어 설명)
6. 상위 limit개 반환 (기본 10개)

**함수**:
- `get_recommendations(user_id, limit)`: 실시간 추천 생성
- `_filter_by_skill_graph()`: 스킬 매칭 필터링
- `_calculate_match_score_and_reason()`: 점수 및 사유 계산
- `get_skill_statistics()`: 스킬 통계 조회

### 5.3 권한 관리 (`job/permissions.py`)
- **HasSimpleSecretKey**: `X-API-KEY` 헤더 검증
- `settings.API_SECRET_KEY`와 비교

## 6. 외부 의존성 분석

### 6.1 agent 앱 의존성 ⚠️
- **현재**: `job/views.py`의 `JobSearchView`가 `agent.tools.vector_search_job_postings_tool` 사용
- **문제**: agent 앱은 deprecated 예정
- **해결**: search app으로 이동 시 의존성 제거 필요

### 6.2 common 앱 의존성
- `common.graph_db.graph_db_client`: Neo4j 연결 (싱글톤)
- `common.vector_db.vector_db_client`: ChromaDB 연결 (싱글톤)
- **중요**: 모든 앱에서 공통 클라이언트 재사용

## 7. 테스트 코드 분석 (`job/tests.py`)

### 7.1 테스트 클래스
1. **TestResumeAnalysis**: 이력서 분석 함수 테스트
   - 경력 연차 추출 (한국어/영어)
   - LLM 분석 성공/실패/Fallback

2. **TestJobPostingSignals**: JobPosting 저장 시그널 테스트
   - Vector DB 및 Graph DB 저장 검증
   - ⚠️ 현재 시그널 기반이지만 Celery 태스크로 변경됨

3. **TestAgentTools**: agent.tools 테스트
   - ⚠️ deprecated 예정

4. **TestJobViews**: API 엔드포인트 테스트
   - JobSearchView
   - RelatedJobsView

### 7.2 테스트 커버리지 이슈
- **누락**: Celery 태스크 테스트 없음
- **누락**: 추천 엔진 (`recommender.py`) 테스트 없음
- **누락**: 스킬 추출 (`skill_extractor.py`) 테스트 부족

## 8. 데이터베이스 스키마 분석

### 8.1 현재 테이블명
- `agent_job_posting`
- `agent_resume`
- `agent_job_recommendation`

### 8.2 마이그레이션 전략
- 새 앱으로 이동 시 `Meta.db_table`로 기존 테이블명 유지
- `--fake` 마이그레이션으로 테이블 재할당

## 9. URL 라우팅 분석 (`config/urls.py`, `job/urls.py`)

### 9.1 현재 URL 구조
```
/api/v1/job-postings/
/api/v1/resumes/
/api/v1/recommendations/
/api/v1/recommendations/for-user/<user_id>/
/api/v1/search/
/api/v1/related-by-skill/<skill_name>/
/api/v1/recommend/
```

### 9.2 RESTful 개선 필요
- 중복 엔드포인트 정리
- 일관된 URL 네이밍

## 10. 설정 파일 분석 (`config/settings.py`)

### 10.1 INSTALLED_APPS
- `agent` ⚠️ deprecated 예정
- `job.apps.JobConfig`
- `user`

### 10.2 환경 변수
- `SECRET_KEY`, `API_SECRET_KEY`
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- `GOOGLE_API_KEY` (Gemini)

### 10.3 Celery 설정
- Broker: Redis
- Task time limit: 30분
- Task serializer: JSON

## 11. 모델 간 관계도

```
[User] (user app)
  |
  | 1:1
  |
[Resume]
  |
  | 분석 → analysis_result (JSON)
  | 임베딩 → ChromaDB 'resumes'
  |
  | M:N (through JobRecommendation)
  |
[JobRecommendation]
  |
  | N:1
  |
[JobPosting]
  |
  | 스킬 추출 → skills_required (JSON)
  | 임베딩 → ChromaDB 'job_postings'
  | 관계 → Neo4j (JobPosting)-[:REQUIRES_SKILL]->(Skill)
```

## 12. 리팩토링 우선순위

### Phase 2 순서 (의존성 기반)
1. **skill app** (가장 독립적)
   - `skill_extractor.py` 이동
   - 다른 앱에서 import 필요

2. **search app**
   - `JobSearchView` 이동
   - `agent.tools` 의존성 제거

3. **job_posting app**
   - JobPosting 모델, ViewSet, tasks
   - Neo4j, ChromaDB 연동

4. **resume app**
   - Resume 모델, ViewSet, tasks
   - LLM 연동

5. **recommendation app** (가장 복잡)
   - JobRecommendation 모델
   - `recommender.py` 이동
   - job_posting, resume 의존

## 13. 주요 리스크 및 해결 방안

### 리스크 1: 순환 의존성
- **원인**: recommendation → job_posting ← resume
- **해결**: Service Layer 도입, 지연 import 사용

### 리스크 2: agent 앱 의존성
- **원인**: `JobSearchView`가 `agent.tools` 사용
- **해결**: search app으로 기능 이동 후 agent 제거

### 리스크 3: 테이블명 불일치
- **원인**: 테이블명이 `agent_*`로 시작
- **해결**: `Meta.db_table`로 유지, 나중에 rename 고려

### 리스크 4: Celery 작업 경로 변경
- **원인**: tasks.py 이동 시 등록된 작업명 변경
- **해결**: `@shared_task(name='...')` 명시적 이름 지정

## 14. 다음 단계

### Phase 1.2: 테스트 환경 구축
- [ ] 기존 테스트 실행 및 통과 확인
- [ ] 테스트 커버리지 측정
- [ ] 누락된 테스트 작성 (Celery, recommender, skill_extractor)
- [ ] 테스트 실행 자동화

### Phase 1.3: 새로운 앱 구조 생성
- [ ] Docker 컨테이너 접속
- [ ] 5개 앱 생성 (skill, search, job_posting, resume, recommendation)
- [ ] INSTALLED_APPS 등록
- [ ] 기본 구조 파일 생성

---

## 📌 결론

현재 `job` app은 과도하게 많은 책임을 가지고 있으며, 다음 문제점이 확인되었습니다:

1. **단일 책임 원칙 위반**: 채용공고, 이력서, 추천, 스킬 추출, 검색 기능이 모두 한 앱에 혼재
2. **agent 앱 의존성**: deprecated 예정인 앱에 대한 의존성 존재
3. **테스트 부족**: 핵심 비즈니스 로직 테스트 누락
4. **중복 엔드포인트**: 실시간 추천 API 중복
5. **테이블명 불일치**: `agent_*` 테이블명이지만 `job` 앱에서 관리

리팩토링을 통해 이러한 문제를 해결하고, 유지보수성과 확장성을 크게 향상시킬 수 있습니다.

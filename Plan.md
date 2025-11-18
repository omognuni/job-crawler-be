# Job Crawler 백엔드 개선 계획서

## 목표
AI 비용 절감 및 응답 속도 개선을 위한 아키텍처 재설계

## 에이전트 역할 분담

### 🔧 Agent 1: Implementation Agent (구현 담당)
- 새로운 기능 구현
- 기존 코드 리팩토링
- 데이터베이스 마이그레이션
- 설정 파일 업데이트

### 🧪 Agent 2: Testing Agent (테스트 담당)
- 단위 테스트 작성
- 통합 테스트 작성
- 테스트 픽스처 및 모킹 설정
- 테스트 커버리지 확인

---

## 1단계: 비동기 기반 구축 (Celery + Redis)

### Agent 1 - 구현 작업 ✅ 완료
- [x] `pyproject.toml`에 `celery>=5.4.0`, `redis>=5.0.7` 의존성 추가
- [x] `docker-compose.prod.yml`에 `redis` 서비스 추가 (`redis:alpine`)
- [x] `docker-compose.prod.yml`에 `celery_worker` 서비스 추가
  - `command`: `uv run celery -A app.config worker -l info -c 2`
  - `depends_on`: `app`, `redis`
- [x] `app/config/celery.py` 파일 생성 및 Celery 앱 정의
- [x] `app/config/__init__.py`에 Celery 앱 로드 코드 추가
- [x] `app/config/settings.py`에 Celery 설정 추가
  - `CELERY_BROKER_URL = 'redis://redis:6379/0'`
  - `CELERY_RESULT_BACKEND = 'redis://redis:6379/0'`

#### 추가 완료 사항 (보안 강화)
- [x] 하드코딩된 Neo4j 비밀번호를 환경 변수로 이동
- [x] SECRET_KEY와 API_SECRET_KEY 분리
- [x] 보안 헤더 설정 (XSS, HSTS, CORS 등)
- [x] Docker non-root 사용자 설정
- [x] 비밀번호 복잡도 검증 추가
- [x] SECURITY.md 문서 작성

### Agent 2 - 테스트 작업 ✅ 완료
- [x] `tests/test_celery_config.py` 생성
  - Celery 앱 초기화 테스트
  - Redis 연결 테스트
- [x] `tests/conftest.py`에 Celery 테스트용 픽스처 추가
  - `@pytest.fixture` celery_app
  - `@pytest.fixture` celery_worker
  - `@pytest.fixture` celery_eager_mode
- [x] Celery worker 시작/중지 테스트
- [x] 간단한 더미 태스크로 비동기 작업 실행 테스트

#### 추가 완료 테스트
- [x] Celery 브로커 설정 테스트
- [x] Celery 직렬화 설정 테스트
- [x] Celery 타임존 설정 테스트
- [x] Celery 태스크 타임아웃 설정 테스트
- [x] 총 9개 테스트 모두 통과 ✅

---

## 2단계: LLM-Free 스킬 추출기 구현

### Agent 1 - 구현 작업 ✅ 완료
- [x] Neo4j에 `Skill` 노드 모델 정의
  - `Skill` 노드는 `name` 속성으로 저장
  - `(JobPosting)-[:REQUIRES_SKILL]->(Skill)` 관계 정의
- [x] 마스터 스킬 목록 시드 데이터 준비
  - 총 85개 스킬 정의 (Backend, Frontend, Mobile, DB, Cloud/DevOps, Tools, Data/AI)
  - 각 스킬별 정규식 패턴 (영어/한글 포함)
- [x] `app/job/skill_extractor.py` 생성
  - `extract_skills(text: str) -> list[str]` 함수 구현
  - `extract_skills_from_job_posting()` 함수 추가
  - `@lru_cache` 데코레이터로 패턴 컴파일 캐싱
  - 정규식 패턴 매칭 로직 (대소문자 무시)
- [x] Neo4j 쿼리 최적화 (스킬 목록 캐싱)
  - `get_all_skills()` 메서드 추가 (@lru_cache)
  - `get_skill_statistics()` 메서드 추가
  - `create_skill_index()` 메서드 추가 (성능 향상)

### Agent 2 - 테스트 작업 ✅ 완료
- [x] `tests/job/test_skill_extractor.py` 생성
- [x] 스킬 추출 기본 테스트
  - "Python과 Django 경험 필수" → `['Django', 'Python']` ✅
  - "C++, Java 개발자" → `['C++', 'Java']` ✅
- [x] 대소문자 무시 테스트
  - lowercase, UPPERCASE, MixedCase 모두 인식 ✅
- [x] 특수문자 처리 테스트 (C++, C#)
  - C++, C#, Vue.js 정상 인식 ✅
- [x] 한글 패턴 테스트
  - 파이썬, 장고, 리액트 인식 ✅
- [x] 동의어/별칭 처리 테스트
  - js→JavaScript, postgres→PostgreSQL, k8s→Kubernetes ✅
- [x] 빈 텍스트, None 입력 엣지 케이스 테스트 ✅
- [x] 성능 테스트 (1000자 텍스트 0.1초 이내 처리) ✅
- [x] 총 29개 테스트 모두 통과 ✅

---

## 3단계: JobPosting 수집 파이프라인 개편

### Agent 1 - 구현 작업 ✅ 완료
- [x] `app/job/tasks.py` 생성 및 `process_job_posting(posting_id)` Celery 태스크 구현
  1. `posting_id`로 `JobPosting` 조회 ✅
  2. `skill_extractor`로 스킬 추출 → `skills_required`, `skills_preferred` 업데이트 ✅
  3. 임베딩 벡터 생성 (노이즈 제거: position + main_tasks + requirements만 사용) ✅
  4. ChromaDB 'job_postings' 컬렉션에 upsert ✅
  5. Neo4j에 `(JobPosting)-[:REQUIRES_SKILL]->(Skill)` 관계 생성 ✅
  6. 에러 핸들링 및 재시도 로직 (max_retries=3, countdown=60초) ✅
- [x] `app/job/models.py`의 `JobPosting.save()` 오버라이드
  - `transaction.on_commit()`로 `process_job_posting.delay()` 호출 ✅
  - 무한 루프 방지 (update_fields로 스킬만 업데이트 시 태스크 스킵) ✅
- [x] `app/job/signals.py`의 `JobPosting` 관련 시그널 **모두 제거** ✅
  - `embed_job_posting_on_save` @receiver 제거 ✅
  - 주석으로 마이그레이션 가이드 추가 ✅
- [x] 임베딩 함수 리팩토링 (노이즈 제거 로직) ✅
  - 회사 소개, 위치, 복지 등 제외 ✅
  - 핵심 정보만 임베딩 (position, main_tasks, requirements, preferred_points) ✅

### Agent 2 - 테스트 작업 ✅ 완료
- [x] `tests/job/test_tasks_job_posting.py` 생성
- [x] `process_job_posting` 태스크 단위 테스트
  - Mock JobPosting 객체 생성
  - 스킬 추출 검증
  - ChromaDB upsert 호출 검증 (mock)
  - Neo4j 관계 생성 검증 (mock)
- [x] `JobPosting.save()` 통합 테스트
  - 저장 시 Celery 태스크가 큐에 추가되는지 확인
  - `transaction.on_commit` 동작 검증
- [x] 임베딩 텍스트 품질 테스트
  - 노이즈(회사소개, 위치 등) 제거 확인
- [x] 실패 시나리오 테스트
  - 존재하지 않는 posting_id 처리
  - DB 연결 오류 처리

#### 완료된 테스트 목록
- [x] process_job_posting 정상 처리 테스트
- [x] 스킬 추출 검증 테스트
- [x] ChromaDB upsert 검증 테스트
- [x] Neo4j 관계 생성 검증 테스트
- [x] 존재하지 않는 ID 처리 테스트
- [x] 재시도 로직 테스트
- [x] JobPosting 저장 시 태스크 트리거 테스트
- [x] JobPosting 업데이트 시 태스크 트리거 테스트
- [x] 스킬 필드만 업데이트 시 무한 루프 방지 테스트
- [x] transaction.on_commit 동작 검증 테스트
- [x] 임베딩 텍스트 핵심 정보 포함 테스트
- [x] 임베딩 텍스트 노이즈 제거 테스트
- [x] 임베딩 텍스트 형식 테스트
- [x] 존재하지 않는 JobPosting 처리 테스트
- [x] ChromaDB 연결 오류 처리 테스트
- [x] Neo4j 연결 오류 처리 테스트
- [x] 스킬 없는 경우 처리 테스트
- [x] 부분적인 데이터 처리 테스트
- [x] 총 18개 테스트 모두 통과 ✅

---

## 4단계: Resume 수집 파이프라인 개편

### Agent 1 - 구현 작업 ✅ 완료
- [x] `app/job/models.py`의 `Resume` 모델에 필드 추가
  - `experience_summary = models.TextField(null=True, blank=True)` ✅
- [x] Django migration 생성 및 실행
  - `0003_resume_experience_summary.py` 생성 ✅
  - 마이그레이션 적용 완료 ✅
- [x] `app/job/tasks.py`에 `process_resume(user_id)` Celery 태스크 구현
  1. `user_id`로 `Resume` 조회 ✅
  2. `needs_analysis()` 체크 (해시 비교) ✅
  3. LLM 호출 (1회) → `analysis_result` + `experience_summary` 동시 추출 ✅
     - 스킬 추출 (LLM-Free, skill_extractor 사용) ✅
     - Gemini API로 경력 연차, 강점, 경력 요약 추출 ✅
     - Fallback 로직 (API 키 없을 시) ✅
  4. `Resume` 업데이트 (`update_fields` 사용) ✅
  5. `experience_summary` 임베딩 생성 ✅
  6. ChromaDB 'resumes' 컬렉션에 upsert ✅
- [x] `Resume.save()` 오버라이드
  - 해시 계산 및 저장 ✅
  - `transaction.on_commit()`로 `process_resume.delay()` 호출 ✅
  - 무한 루프 방지 (내용 변경 시에만 태스크 호출) ✅
- [x] `app/job/signals.py`의 `Resume` 관련 시그널 제거
  - signals.py 정리 및 주석 추가 ✅

### Agent 2 - 테스트 작업 ✅ 완료
- [x] `tests/job/test_tasks_resume.py` 생성
- [x] `process_resume` 태스크 단위 테스트
  - Mock Resume 객체
  - `needs_analysis()` 로직 검증
  - LLM 호출 mock 및 응답 파싱 검증
  - `experience_summary` 생성 확인
  - ChromaDB upsert 검증
- [x] `Resume.save()` 통합 테스트
  - 해시값 변경 시에만 재처리 확인
  - 동일 content 저장 시 태스크 스킵 확인
- [x] AI 응답 파싱 테스트
  - 정상 JSON 응답 처리
  - 불완전한 응답 처리
- [x] 재귀 호출 방지 테스트
  - `update_fields` 사용 시 무한루프 방지 확인

#### 완료된 테스트 목록
**TestProcessResumeTask** (7개)
- [x] LLM을 사용한 정상 Resume 처리
- [x] API 키 없이 Resume 처리 (Fallback)
- [x] 스킬 추출 검증
- [x] needs_analysis() 스킵 로직
- [x] ChromaDB upsert 검증
- [x] 존재하지 않는 user_id 처리
- [x] 재시도 로직 테스트

**TestResumeSaveIntegration** (6개)
- [x] Resume 저장 시 태스크 트리거
- [x] Resume content 업데이트 시 태스크 트리거
- [x] 동일 content 저장 시 태스크 스킵
- [x] 분석 결과 필드만 업데이트 시 무한 루프 방지
- [x] 해시값 계산 테스트
- [x] needs_analysis() 로직 테스트

**TestAIResponseParsing** (4개)
- [x] 정상 JSON 응답 처리
- [x] JSON 코드 블록 포함 응답 처리
- [x] 불완전한 JSON 응답 처리 (Fallback)
- [x] LLM 호출 실패 시 Fallback

**TestInfiniteLoopPrevention** (3개)
- [x] update_fields로 무한루프 방지
- [x] 부분 update_fields 태스크 트리거
- [x] 해시값 변경 시 태스크 트리거

**TestEdgeCases** (3개)
- [x] 빈 content Resume 처리
- [x] 매우 긴 content Resume 처리
- [x] 기술 스택 없는 Resume 처리

- [x] 총 23개 테스트 모두 통과 ✅

---

## 5단계: 관리자 커맨드 개편

### Agent 1 - 구현 작업 ✅ 완료
- [x] `app/job/management/commands/process_data.py` 수정 ✅
- [x] `process_job_postings` 함수 리팩토링 ✅
  - ChromaDB 직접 호출 코드 제거 ✅
  - `process_job_posting.delay(posting_id)` 호출로 변경 ✅
  - 배치 처리 기능 추가 (--batch-size 옵션) ✅
  - Celery group으로 병렬 처리 구현 ✅
- [x] `process_resumes` 함수 리팩토링 ✅
  - ChromaDB 직접 호출 코드 제거 ✅
  - `process_resume.delay(user_id)` 호출로 변경 ✅
  - 배치 처리 기능 추가 (--batch-size 옵션) ✅
  - Celery group으로 병렬 처리 구현 ✅
- [x] 진행상황 로깅 개선 (Celery 작업 큐잉 로그) ✅
  - 배치별 진행 상황 표시 ✅
  - --wait 옵션으로 실시간 완료 확인 가능 ✅

### Agent 2 - 테스트 작업 ✅ 완료
- [x] `tests/job/test_process_data_command.py` 생성 ✅
- [x] `process_data` 커맨드 실행 테스트 ✅
  - Mock DB 데이터 준비 ✅
  - 커맨드 실행 후 Celery 태스크 큐잉 확인 ✅
- [x] 대량 데이터 처리 테스트 ✅
  - 250개 JobPosting 큐잉 시뮬레이션 ✅
  - 배치 크기별 처리 확인 ✅
- [x] 빈 데이터베이스 처리 테스트 ✅
- [x] 오류 핸들링 및 엣지 케이스 테스트 ✅
  - --all, --model 플래그 테스트 ✅
  - --batch-size 커스텀 설정 테스트 ✅
  - --wait 타임아웃 테스트 ✅
  - 출력 포맷 테스트 ✅

#### 완료된 테스트 목록
- [x] 인자 없이 실행 시 경고 메시지 표시
- [x] --model jobposting 플래그 테스트
- [x] --model resume 플래그 테스트
- [x] --all 플래그 테스트
- [x] --batch-size 파라미터 테스트
- [x] --wait 파라미터 테스트
- [x] 빈 JobPosting 처리
- [x] 빈 Resume 처리
- [x] 대량 배치 처리 (250개)
- [x] Resume 타임아웃 설정 (LLM 호출 대응)
- [x] 커맨드 출력 포맷 검증
- [x] 총 11개 테스트 모두 통과 ✅

---

## 6단계: 실시간 추천 엔진 구현 (AI-Free)

### Agent 1 - 구현 작업 ✅ 완료
- [x] `app/job/recommender.py` 생성 ✅
- [x] `get_recommendations(user_id: int) -> list[dict]` 함수 구현 ✅
  1. `Resume`에서 `analysis_result.skills` 추출 ✅
  2. ChromaDB 'resumes'에서 이력서 벡터 조회 ✅
  3. ChromaDB 'job_postings'에서 `.query(n_results=50)` 실행 ✅
  4. Neo4j로 스킬 매칭하여 20개로 정제 ✅
  5. 규칙 기반 `match_reason` 생성 ✅
  6. `match_score` 계산 및 정렬 ✅
  7. Top 10 반환 ✅
- [x] `match_reason` 생성 로직 구현 ✅
  - 스킬 매칭 비율 ✅
  - 경력 요구사항 부합 여부 ✅
  - 우대사항 매칭 개수 ✅
- [x] `match_score` 계산 알고리즘 구현 ✅
  - 필수 스킬 매칭 (최대 50점) ✅
  - 우대 스킬 매칭 (최대 30점) ✅
  - 경력 매칭 (최대 20점) ✅
- [x] API 엔드포인트 추가 (`/api/job/recommend/`) ✅
  - `RecommendationsView` 구현 ✅
  - URL 라우팅 설정 ✅
  - 파라미터 검증 (user_id, limit) ✅

### Agent 2 - 테스트 작업 ✅ 완료
- [x] `tests/job/test_recommender.py` 생성 ✅
- [x] `get_recommendations` 통합 테스트 ✅
  - 테스트용 Resume, JobPosting 픽스처 준비 ✅
  - ChromaDB, Neo4j mock 설정 ✅
  - 추천 결과 반환 확인 ✅
- [x] 스킬 매칭 로직 테스트 ✅
  - 정확한 스킬 매칭 점수 계산 검증 ✅
  - 부분 매칭 처리 ✅
- [x] `match_reason` 생성 테스트 ✅
  - 다양한 시나리오별 적절한 메시지 생성 확인 ✅
- [x] `match_score` 계산 테스트 ✅
  - 가중치 합산 검증 ✅
  - 정렬 순서 확인 ✅
- [x] 엣지 케이스 테스트 ✅
  - 스킬 없는 이력서 ✅
  - 매칭되는 공고 0개 ✅
  - 벡터 임베딩 없는 경우 ✅
- [x] API 엔드포인트 테스트 (`tests/job/test_recommendations_api.py`) ✅
  - 파라미터 검증 테스트 (user_id, limit) ✅
  - 정상 추천 요청/응답 테스트 ✅
  - 커스텀 limit 파라미터 테스트 ✅
  - 결과 없는 경우 처리 ✅
  - E2E 통합 테스트 ✅

#### 완료된 테스트 목록
**test_recommender.py** (12개)
- [x] 완벽한 매칭 점수 계산 테스트
- [x] 부분 매칭 점수 계산 테스트
- [x] 스킬 없는 경우 점수 계산 테스트
- [x] 경력 불일치 시 점수 계산 테스트
- [x] Neo4j 스킬 그래프 필터링 테스트
- [x] 전체 추천 플로우 성공 테스트
- [x] 이력서 없는 경우 처리 테스트
- [x] 스킬 없는 경우 처리 테스트
- [x] 벡터 임베딩 없는 경우 처리 테스트
- [x] 스킬 통계 조회 테스트
- [x] match_score 최대값 제한 테스트
- [x] 빈 스킬로 필터링 테스트

**test_recommendations_api.py** (8개)
- [x] user_id 누락 시 400 에러 테스트
- [x] 잘못된 user_id 형식 400 에러 테스트
- [x] 잘못된 limit 형식 400 에러 테스트
- [x] 정상 추천 요청 테스트
- [x] 커스텀 limit 파라미터 테스트
- [x] 결과 없는 경우 테스트
- [x] 전체 통합 E2E 테스트
- [x] 예외 처리 graceful degradation 테스트

- [x] 총 20개 테스트 모두 통과 ✅

---

## 7단계: API 엔드포인트 교체

### Agent 1 - 구현 작업 ✅ 완료
- [x] `app/job/views.py`의 `JobRecommendationViewSet` 수정 ✅
  - CrewAI 호출 코드 제거 (새로운 추천 엔진으로 교체) ✅
  - `recommender.get_recommendations(user_id, limit)` 호출로 변경 ✅
  - 응답 JSON 직렬화 ✅
- [x] 새로운 액션 메서드 추가 (`for_user`) ✅
  - URL 패턴: `/api/v1/recommendations/for-user/<user_id>/` ✅
  - 실시간 추천 생성 ✅
  - 파라미터 검증 (user_id, limit) ✅
- [x] 기존 list 메서드 개선 ✅
  - user_id 필터링 추가 ✅
  - 저장된 추천 목록 조회 ✅
- [x] `agent/crew.py`에 DEPRECATED 주석 추가 ✅
  - CrewAI 코드는 유지하되 더 이상 추천에 사용하지 않음을 명시 ✅
  - 새로운 추천 시스템 안내 추가 ✅
- [x] 응답 시간 로깅 추가 ✅
  - logger.info로 응답 시간 기록 ✅
  - response_time_seconds 필드 응답에 포함 ✅

### Agent 2 - 테스트 작업 ✅ 완료
- [x] `tests/job/test_views_recommendation.py` 생성 ✅
- [x] API 엔드포인트 통합 테스트 ✅
  - 실시간 추천 요청/응답 테스트 ✅
  - 응답 상태 코드 200 확인 ✅
  - 응답 JSON 스키마 검증 ✅
- [x] 응답 시간 테스트 ✅
  - response_time_seconds 필드 포함 확인 ✅
  - 응답 시간 로깅 확인 ✅
- [x] 파라미터 검증 테스트 ✅
  - user_id 검증 (필수, 숫자) ✅
  - limit 검증 (선택, 숫자) ✅
- [x] 에러 핸들링 테스트 ✅
  - 잘못된 파라미터 처리 ✅
  - 추천 결과 없는 경우 처리 ✅
- [x] 저장된 추천 목록 필터링 테스트 ✅
  - user_id로 필터링 ✅
  - 전체 목록 조회 ✅
- [x] E2E 통합 테스트 ✅
  - 실제 추천 엔진과 통합 테스트 ✅

#### 완료된 테스트 목록
- [x] for_user 엔드포인트 정상 작동 테스트
- [x] 커스텀 limit 파라미터 테스트
- [x] 잘못된 user_id 형식 테스트 (404)
- [x] 잘못된 limit 형식 테스트 (400)
- [x] 추천 결과 없는 경우 테스트
- [x] 응답 시간 로깅 테스트
- [x] 저장된 추천 목록 필터링 테스트
- [x] 잘못된 user_id로 필터링 시 에러 테스트
- [x] 전체 추천 목록 조회 테스트
- [x] response_time_seconds 필드 포함 테스트
- [x] E2E 통합 테스트
- [x] 총 11개 테스트 모두 통과 ✅

---

## 완료 후 검증 체크리스트

### Agent 1
- [ ] 모든 마이그레이션 적용 완료
- [ ] `signals.py`에 불필요한 코드 제거 확인
- [ ] Docker Compose 빌드 및 실행 성공
- [ ] Celery worker 정상 실행 확인
- [ ] Redis 연결 정상 확인
- [ ] 기존 API 엔드포인트 호환성 유지

### Agent 2
- [ ] 테스트 커버리지 80% 이상 달성
- [ ] 모든 단위 테스트 통과
- [ ] 모든 통합 테스트 통과
- [ ] CI/CD 파이프라인 통과
- [ ] 성능 벤치마크 기록
- [ ] 테스트 문서 작성

---

## 협업 가이드라인

### 순차적 의존성
1. **1단계 완료** → 3, 4, 5단계 시작 가능
2. **2단계 완료** → 3단계의 스킬 추출 로직 구현 가능
3. **3, 4단계 완료** → 6단계 추천 엔진 구현 가능
4. **6단계 완료** → 7단계 API 교체 가능

### 동시 작업 가능 영역
- Agent 1이 1단계 구현 중 → Agent 2는 1단계 테스트 코드 작성 (픽스처 준비)
- Agent 1이 2단계 구현 중 → Agent 2는 2단계 테스트 케이스 설계
- 각 단계별 Agent 1 구현 완료 즉시 → Agent 2 테스트 작성 시작

### 커뮤니케이션
- 각 단계 완료 시 상대 에이전트에게 알림
- 테스트 실패 발견 시 즉시 공유
- 설계 변경 필요 시 협의

---

## 예상 소요 시간

| 단계 | 구현 시간 | 테스트 시간 | 총 시간 |
|------|-----------|-------------|---------|
| 1단계 | 2시간 | 1.5시간 | 3.5시간 |
| 2단계 | 3시간 | 2시간 | 5시간 |
| 3단계 | 4시간 | 3시간 | 7시간 |
| 4단계 | 4시간 | 3시간 | 7시간 |
| 5단계 | 1시간 | 1시간 | 2시간 |
| 6단계 | 5시간 | 4시간 | 9시간 |
| 7단계 | 2시간 | 2시간 | 4시간 |
| **합계** | **21시간** | **16.5시간** | **37.5시간** |

---

## 성공 지표

- ✅ AI API 호출 횟수: 기존 대비 **95% 감소**
- ✅ 추천 응답 시간: **0.1초 이내**
- ✅ 시스템 안정성: 99% 이상 가동률
- ✅ 테스트 커버리지: 80% 이상
- ✅ Celery 작업 성공률: 98% 이상

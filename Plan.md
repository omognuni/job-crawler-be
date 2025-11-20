# Job Crawler Backend 리팩토링 계획

## 📋 목표
- `job` app의 과도한 책임을 도메인별로 분리 (Resume, Recommendation을 별도 앱으로)
- `job` app은 채용 공고(JobPosting)만 관리하도록 유지
- 유지보수성과 확장성 향상
- deprecated된 `agent` app 정리
- Service Layer 패턴 도입

---

## 🎯 Phase 1: 준비 및 분석 (1-2주)

### 1.1 현재 코드 분석
- [ ] `job/models.py` 전체 모델 파악 (JobPosting, Resume, JobRecommendation)
- [ ] `job/views.py` 엔드포인트 및 비즈니스 로직 분석 (각 모델별로 분류)
- [ ] `job/tasks.py` Celery 작업 의존성 파악 (job vs resume 처리)
- [ ] `job/serializers.py` 시리얼라이저 의존성 분석
- [ ] 모델 간 관계도 작성 (ForeignKey, ManyToMany 관계 파악)
- [ ] 이동 대상 정리: Resume, JobRecommendation → 새 앱 / JobPosting → job 앱 유지

### 1.2 테스트 환경 구축
- [ ] 기존 테스트 코드 실행 및 통과 확인
- [ ] 테스트 커버리지 측정
- [ ] 리팩토링 기준 테스트 스위트 확립

### 1.3 새로운 앱 구조 생성
- [ ] `app/resume/` 앱 생성 (이력서)
- [ ] `app/recommendation/` 앱 생성 (추천 시스템)
- [ ] `app/skill/` 앱 생성 (스킬 추출 및 관리)
- [ ] `app/search/` 앱 생성 (검색 기능)
- [ ] 각 앱의 기본 구조 생성 (models.py, views.py, serializers.py, services.py, tasks.py, urls.py)
- [ ] 기존 `app/job/` 앱은 유지 (채용 공고만 관리)

---

## 🔄 Phase 2: 점진적 마이그레이션 (2-3주)

### 2.1 `skill` app 분리 (가장 독립적)
- [ ] `job/skill_extractor.py` → `skill/services.py`로 이동
- [ ] 스킬 관련 유틸리티 함수 이동
- [ ] `/api/v1/related-by-skill/<skill_name>/` 엔드포인트 이동
- [ ] 단위 테스트 작성 및 검증
- [ ] 기존 코드에서 임포트 경로 업데이트

### 2.2 `search` app 분리
- [ ] 검색 관련 뷰 로직 추출
- [ ] `SearchService` 클래스 생성
- [ ] `/api/v1/search/` 엔드포인트 이동
- [ ] 벡터 검색 로직을 Service Layer로 분리
- [ ] 단위 테스트 작성 및 검증

### 2.3 `job` app 정리 (채용 공고만 남김)
- [ ] `Resume` 모델을 `resume/` 앱으로 이동 준비
- [ ] `JobRecommendation` 모델을 `recommendation/` 앱으로 이동 준비
- [ ] `JobPosting` 모델 및 관련 로직은 `job/` 앱에 유지
- [ ] `JobService` 생성 (채용 공고 비즈니스 로직)
- [ ] `process_job_posting_task` Celery 작업 유지 및 리팩토링
- [ ] Neo4j/ChromaDB 연동 로직을 Service에 캡슐화
- [ ] 단위 테스트 및 통합 테스트

### 2.4 `resume` app 분리
- [ ] `job/models.py`에서 `Resume` 모델 → `resume/models.py`로 이동
- [ ] `job/serializers.py`에서 `ResumeSerializer` 이동
- [ ] `job/views.py`에서 Resume CRUD 엔드포인트 이동
- [ ] `ResumeService` 생성 (분석 로직 포함)
- [ ] `job/tasks.py`에서 `process_resume_task` → `resume/tasks.py`로 이동
- [ ] 이력서 분석 로직을 Service에 캡슐화
- [ ] 모든 import 경로 업데이트 (`from job.models import Resume` → `from resume.models import Resume`)
- [ ] 단위 테스트 및 통합 테스트

### 2.5 `recommendation` app 분리
- [ ] `job/models.py`에서 `JobRecommendation` 모델 → `recommendation/models.py`로 이동
- [ ] `job/serializers.py`에서 `JobRecommendationSerializer` 이동
- [ ] `job/views.py`에서 Recommendation CRUD 엔드포인트 이동
- [ ] `job/recommender.py` → `recommendation/services.py`로 이동
- [ ] 추천 엔드포인트 통합 (중복 제거)
  - `/api/v1/recommendations/for-user/<user_id>/` 유지
  - `/api/v1/recommend/` 제거
- [ ] `RecommendationService` 생성 (하이브리드 추천 로직)
- [ ] 모든 import 경로 업데이트
- [ ] 단위 테스트 및 통합 테스트

---

## 🏗️ Phase 3: Service Layer 패턴 도입 (1-2주)

### 3.1 각 앱에 Service Layer 구현
```
job/
├── models.py         # JobPosting 모델만
├── views.py          # API 인터페이스만 (thin controller)
├── serializers.py
├── services.py       # 채용 공고 비즈니스 로직
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
- [x] `JobService`: 채용 공고 생성/수정/삭제 로직 (`job/services.py`)
- [x] `ResumeService`: 이력서 분석 및 처리 로직
- [x] `RecommendationService`: 하이브리드 추천 엔진
- [x] `SkillExtractionService`: 스킬 추출 로직
- [x] `SearchService`: 벡터/하이브리드 검색 로직

### 3.3 View를 Thin Controller로 리팩토링
- [x] 비즈니스 로직을 Service로 위임
- [x] View는 요청/응답 처리만 담당
- [x] 예외 처리 및 로깅 추가

---

## 🧹 Phase 4: 정리 및 최적화 (1주)

### 4.1 기존 코드 정리
- [x] `job/` app에서 이동된 파일 확인 및 제거 (Resume, JobRecommendation 관련)
- [x] `job/` app은 유지 (JobPosting만 관리)
- [x] 사용되지 않는 import 정리
- [x] Backward compatibility imports 추가 (job/models.py, job/recommender.py)

### 4.2 `agent` app 처리
- [x] agent app 사용 여부 최종 확인
- [x] 옵션 A: 완전 제거 ✅
- [x] app/agent 디렉토리 삭제 완료

### 4.3 URL 라우팅 재구성
```python
# config/urls.py
urlpatterns = [
    path('api/v1/jobs/', include('job.urls')),              # 채용 공고
    path('api/v1/resumes/', include('resume.urls')),        # 이력서
    path('api/v1/recommendations/', include('recommendation.urls')),  # 추천
    path('api/v1/skills/', include('skill.urls')),          # 스킬
    path('api/v1/search/', include('search.urls')),         # 검색
]
```
- [x] 중복 엔드포인트 제거
- [x] RESTful 원칙에 맞게 URL 정리 (user → users, job-postings → jobs)
- [x] API 버전 관리 전략 수립

### 4.4 설정 파일 정리
- [x] `INSTALLED_APPS`에서 agent 제거
- [x] `INSTALLED_APPS`에 common 추가
- [x] 새로운 앱들 이미 등록됨 (resume, recommendation, skill, search)
- [x] `job` 앱은 이미 등록되어 있으므로 유지

---

## 🧪 Phase 5: 테스트 및 검증 (1주)

### 5.1 테스트 구조 변경
- [x] 각 앱에 `tests/` 디렉토리 생성
- [x] 기존 `tests.py` 파일 삭제
- [x] `test_services.py`, `test_views.py` 분리

### 5.2 테스트 작성
- [x] `job/tests/`: JobService, JobPostingViewSet 테스트
- [x] `resume/tests/`: ResumeService, ResumeViewSet 테스트
- [x] `recommendation/tests/`: RecommendationService, 추천 API 테스트
- [x] `skill/tests/`: SkillExtractionService 테스트
- [x] `search/tests/`: SearchService, 검색 API 테스트
- [x] 성능 테스트 작성 (추천 시스템 응답 시간)

### 5.3 문서화
- [x] 프로젝트 README.md 작성 (기술 스택, 설치, API)
- [x] 각 앱의 README.md 작성
  - [x] job/README.md
  - [x] resume/README.md
  - [x] recommendation/README.md
- [x] API 문서 (Swagger UI 제공: `/api/v1/schema/swagger-ui/`)

### 5.4 테스트 실행
```bash
# 전체 테스트
pytest

# 커버리지 측정
pytest --cov=app --cov-report=html

# 특정 앱 테스트
pytest app/job/tests/
pytest app/resume/tests/
pytest app/recommendation/tests/

# 성능 테스트
pytest app/tests/performance/
```

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

## 📝 주의사항

1. **점진적 접근**: 한 번에 모든 것을 변경하지 말고 단계별로 진행
2. **테스트 우선**: 각 단계마다 테스트 작성 및 검증
3. **백워드 호환성**: 기존 API 사용자를 위한 호환성 유지 (필요시 deprecated 경고)
4. **문서화**: 변경사항을 즉시 문서화
5. **코드 리뷰**: 각 단계마다 팀원과 코드 리뷰 수행

---

## 🚀 시작하기

리팩토링을 시작하려면:
1. 이 계획서를 팀과 공유하고 피드백 받기
2. Phase 1.1부터 체크리스트를 하나씩 완료
3. 각 Phase 완료 후 회고 및 다음 Phase 조정

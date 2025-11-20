# Phase 1.4: 추가 분석 결과

## 📊 분석 일자
2025년 11월 20일

## 1. 데이터베이스 스키마 분석

### 1.1 기본 정보
- **Database**: `crawler` (PostgreSQL 15.14)
- **Schema**: `public`
- **Encoding**: UTF8

### 1.2 테이블 목록
1. `agent_job_posting` - 채용 공고
2. `agent_resume` - 이력서
3. `agent_job_recommendation` - 추천 결과

### 1.3 agent_job_posting 스키마

```sql
Table: agent_job_posting
Primary Key: posting_id (integer)
Indexes:
  - agent_job_posting_pkey (PRIMARY KEY, btree)

Columns:
  posting_id       integer NOT NULL
  url              varchar(255) NOT NULL
  company_name     varchar(255) NOT NULL
  position         varchar(255) NOT NULL
  main_tasks       text NOT NULL
  requirements     text NOT NULL
  preferred_points text NOT NULL
  location         varchar(255) NOT NULL
  district         varchar(255) NOT NULL
  employment_type  varchar(255) NOT NULL
  career_min       integer NOT NULL
  career_max       integer NOT NULL
  created_at       timestamptz NOT NULL
  updated_at       timestamptz NOT NULL
  skills_preferred text
  skills_required  jsonb

Foreign Key References:
  Referenced by: agent_job_recommendation.job_posting_id

Row Count: 2,671
```

**마이그레이션 전략**:
- `Meta.db_table = 'agent_job_posting'`로 테이블명 유지
- 데이터 손실 없이 `job_posting` 앱으로 이동 가능

**인덱스 고려사항**:
- `posting_id`만 인덱스 존재
- 검색 성능 향상을 위한 추가 인덱스 필요:
  - `company_name` (회사명 검색)
  - `position` (포지션 검색)
  - `created_at` (최신 공고 조회)
  - `skills_required` (JSONB gin index for skill search)

### 1.4 agent_resume 스키마

```sql
Table: agent_resume
Primary Key: id (bigint)
Indexes:
  - agent_resume_pkey (PRIMARY KEY, btree)
  - agent_resume_user_id_key (UNIQUE, btree)

Columns:
  id                 bigint NOT NULL (identity)
  user_id            integer NOT NULL (unique)
  content            text NOT NULL
  content_hash       varchar(64) NOT NULL
  analysis_result    jsonb
  analyzed_at        timestamptz
  created_at         timestamptz NOT NULL
  updated_at         timestamptz NOT NULL
  experience_summary text

Row Count: 1
```

**마이그레이션 전략**:
- `Meta.db_table = 'agent_resume'`로 테이블명 유지
- `user_id`에 UNIQUE 제약조건 존재 (1:1 관계)
- 데이터 손실 없이 `resume` 앱으로 이동 가능

**인덱스 고려사항**:
- `user_id` 인덱스 이미 존재 (UNIQUE)
- 추가 인덱스 불필요

### 1.5 agent_job_recommendation 스키마

```sql
Table: agent_job_recommendation
Primary Key: id (bigint)
Indexes:
  - agent_job_recommendation_pkey (PRIMARY KEY, btree)
  - agent_job_recommendation_job_posting_id_2d21c42e (btree)
  - agent_job_recommendation_user_id_rank_created_at_cd9dc68f_uniq (UNIQUE, btree)

Columns:
  id             bigint NOT NULL (identity)
  user_id        integer NOT NULL
  rank           integer NOT NULL
  match_score    double precision NOT NULL
  match_reason   text NOT NULL
  created_at     timestamptz NOT NULL
  job_posting_id integer NOT NULL

Foreign Keys:
  job_posting_id -> agent_job_posting(posting_id) DEFERRABLE INITIALLY DEFERRED

Unique Constraint:
  (user_id, rank, created_at)

Row Count: 20
```

**마이그레이션 전략**:
- `Meta.db_table = 'agent_job_recommendation'`로 테이블명 유지
- Foreign Key 관계 유지 필요
- `job_posting` 앱 마이그레이션 후 이동해야 함 (의존성)

**인덱스 고려사항**:
- `job_posting_id` 인덱스 이미 존재
- Unique constraint로 중복 추천 방지
- 추가 인덱스 불필요

### 1.6 데이터 분포
| 테이블 | Row Count | 용도 |
|--------|-----------|------|
| agent_job_posting | 2,671 | 실제 채용 공고 데이터 |
| agent_resume | 1 | 테스트용 이력서 1개 |
| agent_job_recommendation | 20 | 추천 결과 (10개 x 2회) |

### 1.7 테이블 관계도

```
┌─────────────────────┐
│  agent_resume       │
│  (1 row)            │
└─────────────────────┘
          ↑ user_id (1:N, via application)
          │
┌─────────────────────┐
│ agent_job_          │
│ recommendation      │
│ (20 rows)           │
└─────────────────────┘
          ↓ job_posting_id (N:1, FK)
          │
┌─────────────────────┐
│ agent_job_posting   │
│ (2,671 rows)        │
└─────────────────────┘
```

## 2. 외부 서비스 버전 분석

### 2.1 PostgreSQL
- **Version**: 15.14 (Debian 15.14-1.pgdg13+1)
- **Image**: postgres:15
- **Port**: 5432
- **Database**: crawler
- **Status**: ✅ 정상

**주의사항**:
- PostgreSQL 15는 2027년 11월까지 지원
- JSONB 성능 최적화 필요 (GIN 인덱스)
- 정기 VACUUM 필요

### 2.2 Neo4j
- **Version**: 5.26.16 (Neo4j Kernel)
- **Image**: neo4j:5
- **Port**: 7474 (HTTP), 7687 (Bolt)
- **Status**: ✅ 정상

**사용 목적**:
- (JobPosting)-[:REQUIRES_SKILL]->(Skill) 관계 그래프
- 스킬 기반 공고 검색
- 스킬 통계 및 트렌드 분석

**백업 전략**:
```bash
docker exec neo4j neo4j-admin dump --database=neo4j --to=/backups/neo4j-backup.dump
```

### 2.3 ChromaDB
- **Version**: 1.2.1
- **Image**: chromadb/chroma
- **Port**: 8008 → 8000 (내부)
- **Status**: ✅ 정상

**사용 목적**:
- 채용 공고 벡터 임베딩 (collection: `job_postings`)
- 이력서 벡터 임베딩 (collection: `resumes`)
- 의미론적 유사도 검색

**백업 전략**:
```bash
# ChromaDB 데이터 디렉토리 백업
docker exec chromadb tar -czf /backups/chroma-backup.tar.gz /chroma/data
```

**주의사항**:
- ChromaDB 1.2.1은 최신 버전 (2025.11 기준)
- 임베딩 모델 변경 시 전체 재임베딩 필요
- 컬렉션 이름 변경 불가 (재생성 필요)

### 2.4 Redis
- **Version**: 8.2.3
- **Image**: redis:alpine
- **Port**: 6379
- **Status**: ✅ 정상

**사용 목적**:
- Celery 브로커 (작업 큐)
- Celery 결과 백엔드
- 캐싱 (향후 계획)

**백업 전략**:
```bash
# Redis RDB 백업
docker exec redis redis-cli BGSAVE
docker cp redis:/data/dump.rdb ./backups/redis-backup.rdb
```

### 2.5 외부 API: Google Gemini
- **Model**: gemini-2.0-flash
- **사용처**: `resume/tasks.py::process_resume`
- **API Key**: 환경 변수 `GOOGLE_API_KEY`
- **Fallback**: LLM 실패 시 정규식 기반 분석

**비용 최적화**:
- 이력서 해시 비교로 불필요한 LLM 호출 방지
- Temperature: 0.1 (일관성 중시)
- Max tokens: 400 (비용 절감)

### 2.6 버전 호환성 매트릭스

| Service | Current Version | EOL Date | Upgrade Priority |
|---------|-----------------|----------|------------------|
| PostgreSQL | 15.14 | 2027-11 | Low (stable) |
| Neo4j | 5.26.16 | 2028-Q2 | Low (LTS) |
| ChromaDB | 1.2.1 | - | Medium (fast-moving) |
| Redis | 8.2.3 | - | Low (stable) |
| Django | 5.2.7 | 2026-04 | Low (LTS) |
| Python | 3.13.9 | 2029-10 | Low (latest) |

## 3. permissions.py 분석

### 3.1 코드 구조
```python
class HasSimpleSecretKey(BasePermission):
    """
    'X-API-KEY' 헤더에 유효한 API 키가 있는지 확인합니다.
    """

    def has_permission(self, request, view):
        expected_key = settings.API_SECRET_KEY
        provided_key = request.headers.get("X-API-KEY")
        return provided_key == expected_key
```

### 3.2 사용 현황
**settings.py**:
```python
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "job.permissions.HasSimpleSecretKey",  # 전역 적용
    ],
}
```

**영향도**: 🔴 **높음** (전역 권한 클래스)

### 3.3 마이그레이션 계획
**옵션 1**: `common` app으로 이동 (권장)
```python
# common/permissions.py
class HasSimpleSecretKey(BasePermission):
    # ... 동일 로직

# settings.py
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "common.permissions.HasSimpleSecretKey",
    ],
}
```

**옵션 2**: 각 앱에 복사
- job_posting, resume, recommendation 각각 권한 클래스 정의
- 중복 코드 발생 (비추천)

**결정**: `common.permissions`로 이동

### 3.4 보안 검토
**현재 방식**:
- 단순 API 키 비교 (Basic Auth 수준)
- HTTPS 필수 (키 노출 방지)

**개선 사항 (선택)**:
- JWT 인증으로 업그레이드 고려
- Rate limiting 추가
- API 키 만료 기능

## 4. recommender.py 의존성 분석

### 4.1 코드 구조 (요약)
```python
# job/recommender.py

def get_recommendations(user_id: int, limit: int = 10) -> List[Dict]:
    """
    하이브리드 추천 엔진 (Vector + Graph)

    의존성:
    - Resume 모델 (job app)
    - JobPosting 모델 (job app)
    - ChromaDB (common.vector_db)
    - Neo4j (common.graph_db)
    - skill_extractor (job app)
    """
    # 1. Resume에서 사용자 스킬 추출
    resume = Resume.objects.get(user_id=user_id)
    user_skills = resume.analysis_result.get("skills", [])

    # 2. ChromaDB 벡터 유사도 검색 (50개)
    # 3. Neo4j 스킬 그래프 매칭 (20개)
    # 4. 매칭 점수 계산 (10개)
```

### 4.2 의존성 그래프
```
recommender.py
    ├── job.models.Resume ──────┐
    ├── job.models.JobPosting ──┤
    ├── job.skill_extractor ────┤ job app 의존성 (3개)
    ├── common.vector_db ───────┤
    └── common.graph_db ────────┴ common app 의존성 (2개)
```

### 4.3 마이그레이션 전략

**Phase 2.5: recommendation app 분리 시**

1. **Import 경로 업데이트**:
```python
# Before
from job.models import Resume, JobPosting
from job.skill_extractor import extract_skills

# After
from resume.models import Resume
from job_posting.models import JobPosting
from skill.services import SkillExtractionService
```

2. **Service 클래스로 리팩토링**:
```python
# recommendation/services.py
class RecommendationService:
    def __init__(self, vector_db_client, graph_db_client):
        self.vector_db = vector_db_client
        self.graph_db = graph_db_client

    def get_recommendations(self, user_id: int, limit: int = 10):
        # 기존 로직 이동
        pass
```

3. **순환 의존성 방지**:
- Resume, JobPosting 모델은 먼저 이동
- recommendation은 가장 마지막에 이동
- 지연 import 사용 (필요 시)

### 4.4 함수별 의존성
| 함수 | 의존성 | 이동 계획 |
|------|--------|----------|
| `get_recommendations` | Resume, JobPosting, Vector DB, Graph DB | → recommendation/services.py |
| `_filter_by_skill_graph` | Graph DB | → recommendation/services.py |
| `_calculate_match_score_and_reason` | JobPosting, skill_extractor | → recommendation/services.py |
| `get_skill_statistics` | Graph DB | → skill/services.py (?) |

**결정**:
- `get_skill_statistics`는 skill 앱으로 이동 고려
- 나머지는 recommendation 앱으로 이동

## 5. 마이그레이션 리스크 평가

### 5.1 데이터 손실 리스크
| 항목 | 리스크 수준 | 대응 방안 |
|------|-------------|----------|
| 테이블 이름 변경 | 🟢 낮음 | `Meta.db_table`로 유지 |
| Foreign Key 관계 | 🟡 중간 | 마이그레이션 순서 준수 |
| JSONB 필드 | 🟢 낮음 | 데이터 타입 동일 유지 |
| 인덱스 | 🟢 낮음 | 자동 재생성 |

### 5.2 서비스 중단 리스크
| 항목 | 리스크 수준 | 대응 방안 |
|------|-------------|----------|
| API 엔드포인트 | 🟡 중간 | URL 변경 없이 라우팅만 변경 |
| Celery 작업 | 🟢 낮음 | 명시적 태스크 이름 지정 |
| 외부 서비스 | 🟢 낮음 | 변경 없음 |

### 5.3 성능 영향
| 항목 | 예상 영향 | 비고 |
|------|----------|------|
| 데이터베이스 쿼리 | 변화 없음 | 테이블 구조 동일 |
| API 응답 시간 | 변화 없음 | 비즈니스 로직 동일 |
| Celery 작업 | 변화 없음 | 작업 내용 동일 |

## 6. 백업 체크리스트

### 6.1 Phase 2 시작 전 백업 (필수)

```bash
#!/bin/bash
# scripts/backup_phase2_start.sh

BACKUP_DIR="./backups/phase2_start_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# 1. PostgreSQL 백업
docker exec db pg_dump -U postgres crawler > "$BACKUP_DIR/postgres.sql"

# 2. Neo4j 백업
docker exec neo4j neo4j-admin dump \
  --database=neo4j \
  --to="$BACKUP_DIR/neo4j.dump"

# 3. ChromaDB 백업
docker exec chromadb tar -czf - /chroma/data > "$BACKUP_DIR/chroma.tar.gz"

# 4. Redis 백업
docker exec redis redis-cli SAVE
docker cp redis:/data/dump.rdb "$BACKUP_DIR/redis.rdb"

# 5. 코드 백업 (Git tag)
git tag -a "backup-phase2-start-$(date +%Y%m%d)" \
  -m "Backup before Phase 2 migration"
git push origin --tags

echo "✅ 백업 완료: $BACKUP_DIR"
```

### 6.2 백업 검증

```bash
# PostgreSQL 백업 검증
psql -U postgres -d test_restore < "$BACKUP_DIR/postgres.sql"

# 파일 크기 확인
ls -lh "$BACKUP_DIR"

# 백업 파일 무결성 검사
md5sum "$BACKUP_DIR"/*.sql > "$BACKUP_DIR/checksums.md5"
```

## 7. 다음 단계

### Phase 1.5: 백업 및 복구 준비
- [ ] 백업 스크립트 작성
- [ ] 백업 실행 및 검증
- [ ] 복구 절차 문서화
- [ ] 롤백 시나리오 테스트

### Phase 2: 점진적 마이그레이션 시작
- [ ] Phase 2.1: skill app 분리
- [ ] Phase 2.2: search app 분리
- [ ] Phase 2.3: job_posting app 분리
- [ ] Phase 2.4: resume app 분리
- [ ] Phase 2.5: recommendation app 분리

---

## 📌 결론

**Phase 1.4 완료**: ✅
- 데이터베이스 스키마 분석 완료 (3개 테이블, 2,692 rows)
- 외부 서비스 버전 확인 완료 (PostgreSQL, Neo4j, ChromaDB, Redis)
- permissions.py 의존성 파악 (`common` app으로 이동 예정)
- recommender.py 의존성 그래프 작성

**주요 발견사항**:
- 테이블명이 `agent_*`로 시작하지만 `Meta.db_table`로 유지 가능
- Foreign Key 관계가 명확하여 마이그레이션 순서 중요
- 외부 서비스 모두 최신 버전 또는 LTS 버전 사용 중
- recommender.py는 5개 모듈 의존 (가장 복잡)

**리팩토링 준비 상태**: ✅ **Ready**
- 데이터베이스 현황 파악 완료
- 의존성 그래프 작성 완료
- 백업 전략 수립 완료

# 벡터 DB 및 그래프 DB 도입 실행 계획

## 1단계: 환경 설정 및 라이브러리 설치

- [x] `pyproject.toml` 파일에 필요한 라이브러리를 추가합니다.
    -   **벡터 DB:** `chromadb` (경량 로컬 DB)
    -   **임베딩 모델:** `sentence-transformers`
    -   **그래프 DB:** `neo4j` (Python 드라이버)
- [x] `uv pip install` 또는 `uv sync` 명령으로 라이브러리를 설치합니다.
- [x] `docker-compose.yml`에 `chromadb`와 `neo4j` 서비스 컨테이너를 추가하여 로컬 개발 환경을 구성합니다.

## 2단계: 벡터 DB를 이용한 의미 기반 검색 구현

- [x] **`app/common/vector_db.py` 모듈 생성:**
    -   ChromaDB 클라이언트 초기화 및 컬렉션 생성/관리를 위한 헬퍼 함수를 작성합니다.
    -   임베딩 생성 및 벡터 DB 저장을 위한 함수를 작성합니다.
    -   유사도 검색을 수행하는 함수를 작성합니다.
- [x] **`app/agent/tasks.py` 수정:**
    -   채용 공고 데이터를 처리하는 태스크(`process_job_posting_task` 등) 내에서 `vector_db.py`의 함수를 호출하여 임베딩을 생성하고 ChromaDB에 저장하도록 로직을 수정합니다.
    -   **참고:** `tasks.py`를 직접 수정하는 대신, Django Signal을 사용하여 `JobPosting` 모델이 저장될 때마다 자동으로 임베딩을 생성하고 벡터 DB에 저장하도록 구현했습니다. (`app/job/signals.py`)
- [x] **`app/job/views.py` 또는 `app/agent/crew.py` 수정:**
    -   사용자 쿼리가 들어왔을 때, 쿼리를 임베딩하고 `vector_db.py`의 검색 함수를 호출하여 유사한 채용 공고 ID 목록을 가져옵니다.
    -   가져온 ID를 기반으로 DB에서 전체 채용 공고 정보를 조회하여 반환하도록 API 로직을 수정합니다.
    -   **참고:** `app/agent/tools.py`의 `fetch_filtered_job_postings_tool`을 벡터 검색을 사용하는 `vector_search_job_postings_tool`로 교체하고, `app/agent/tasks.py`의 `fetch_job_postings_task`가 이 새로운 툴을 사용하도록 수정했습니다.
- [x] **단위/통합 테스트 작성:**
    -   임베딩 생성, 저장, 검색 기능이 올바르게 동작하는지 확인하는 테스트 코드를 `app/job/tests.py` 또는 별도의 테스트 파일에 작성합니다.

## 3단계: 그래프 DB를 이용한 관계 분석 기능 구현

- [x] **`app/common/graph_db.py` 모듈 생성:**
    -   Neo4j 드라이버 초기화 및 연결을 관리하는 헬퍼 함수를 작성합니다.
    -   Node(e.g., `Skill`, `Company`)와 Relationship(e.g., `REQUIRES_SKILL`)을 생성/수정하는 함수를 작성합니다. (Cypher 쿼리 사용)
- [x] **`app/agent/tasks.py` 수정:**
    -   채용 공고 텍스트에서 정규식, 키워드 매칭, 또는 LLM을 이용해 `Skill`, `Company`, `Location` 등의 핵심 엔티티를 추출하는 로직을 추가합니다.
    -   추출된 엔티티를 `graph_db.py`의 함수를 통해 Neo4j에 저장하도록 로직을 수정합니다.
- [x] **`app/job/urls.py` 및 `views.py` 수정:**
    -   관계 기반 추천 API 엔드포인트를 새로 추가합니다. (e.g., `/api/jobs/recommendations/related-to-skill/{skill_name}/`)
    -   View에서 `graph_db.py`를 사용하여 복잡한 관계를 조회하고 결과를 반환하는 로직을 작성합니다.
- [x] **단위/통합 테스트 작성:**
    -   엔티티 추출 및 그래프 DB 저장 기능, 관계 기반 조회 API가 올바르게 동작하는지 확인하는 테스트 코드를 작성합니다.

## 4단계: 리팩토링 및 최종 검증

- [ ] 기존 LLM 호출 로직을 새로운 DB 기반 조회 로직으로 점진적으로 대체합니다.
- [ ] LLM 사용을 최소화하면서도 검색/추천의 품질이 유지되거나 향상되었는지 검증합니다.
- [ ] 불필요한 코드나 주석을 정리하고, 추가된 설정(`docker-compose.prod.yml` 등)을 프로덕션 환경에 맞게 조정합니다.
- [ ] `README.md`에 새로운 아키텍처와 로컬 환경 설정 방법에 대한 문서를 업데이트합니다.

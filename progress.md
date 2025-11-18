### \#\# 1단계: 비동기 기반 구축 (Celery + Redis)

가장 먼저, 무거운 AI 작업과 임베딩을 Django 요청-응답 사이클에서 완전히 분리하기 위해 비동기 작업 큐를 도입합니다.

1.  **의존성 추가 (`pyproject.toml`):**

      * `[project.dependencies]`에 `celery>=5.4.0`와 `redis>=5.0.7`를 추가합니다.

2.  **인프라 추가 (`docker-compose.prod.yml`):**

      * `redis` 서비스를 추가합니다. (공식 `redis:alpine` 이미지 사용)
      * `celery_worker` 서비스를 추가합니다.
          * `image`: `app` 서비스와 동일한 이미지를 사용합니다. (`${PROD_IMAGE_NAME}`)
          * `command`: `uv run celery -A config worker -l info -c 2` (AI RPM 한계에 맞춰 `-c 2` 동시성 조절)
          * `depends_on`: `app`, `redis`

3.  **Django 설정 (`app/config/`)**:

      * `app/config/celery.py` 파일을 생성하여 Celery 앱을 정의하고 스케줄을 설정합니다.
      * `app/config/__init__.py`에 Celery 앱이 로드되도록 합니다.
      * `app/config/settings.py`에 `CELERY_BROKER_URL`과 `CELERY_RESULT_BACKEND`를 `redis://redis:6379/0`로 설정합니다.

-----

### \#\# 2단계: LLM-Free 스킬 추출기 구현

AI 비용 없이 JD에서 스킬을 추출하는 "딕셔너리 + 정규식" 기반의 재사용 가능한 모듈을 만듭니다.

1.  **스킬 딕셔너리 구축:**

      * `Neo4j` 또는 PostgreSQL에 `Skill` 모델을 만들어 '마스터 스킬 목록'(예: `Python`, `C++`, `AWS`)과 검색 패턴(예: `\bpython\b`, `\bc\+\+\b|\bcpp\b`, `\baws\b`)을 저장합니다.

2.  **모듈 생성 (`app/job/skill_extractor.py`):**

      * `extract_skills(text: str) -> list[str]:` 함수를 구현합니다.
      * 이 함수는 1단계의 딕셔너리를 로드하여(캐싱 권장), 정규화된 텍스트를 스캔하고 매칭되는 스킬 목록을 반환합니다.
      * (`pyproject.toml`에 `neo4j`가 이미 있으므로 `Neo4j`의 `(Skill)` 노드 목록을 활용하는 것이 가장 이상적입니다.)

-----

### \#\# 3단계: `JobPosting` 수집 파이프라인 개편 (명시적 실행)

`JobPosting`이 저장될 때, 시그널(안티패턴) 대신 `save()` 메소드를 오버라이드하여 명시적으로 비동기 작업을 호출합니다.

1.  **Celery 작업 생성 (`app/job/tasks.py`):**

      * `@shared_task` 데코레이터로 `process_job_posting(posting_id)` 함수를 만듭니다.
      * **작업 내용:**
        1.  `posting_id`로 `JobPosting` 객체를 조회합니다.
        2.  `job/skill_extractor.py`를 사용해 `requirements`, `preferred_points`에서 스킬을 추출하여 `skills_required`, `skills_preferred` (JSON) 필드를 업데이트하고 `save()`합니다.
        3.  **[임베딩 개선]** `position` + `main_tasks` + `requirements` 텍스트만 조합하여 임베딩 벡터를 생성합니다. (회사소개, 위치 등 노이즈 제거)
        4.  `ChromaDB`의 'job\_postings' 컬렉션에 `posting_id`와 벡터를 `upsert`합니다.
        5.  `Neo4j`에 `(JobPosting)-[:REQUIRES]->(Skill)` 관계를 업데이트합니다.

2.  **모델 수정 (`app/job/models.py`):**

      * `JobPosting` 모델의 `save()` 메소드를 오버라이드합니다.
      * `signals.py`의 `JobPosting` 관련 로직을 **모두 제거**합니다.

    <!-- end list -->

    ```python
    # app/job/models.py
    from django.db import models, transaction
    from job.tasks import process_job_posting # 1단계에서 만든 Celery 작업

    class JobPosting(models.Model):
        # ... (기존 필드) ...

        def save(self, *args, **kwargs):
            # 1. DB에 먼저 저장
            super().save(*args, **kwargs)

            # 2. 명시적으로 비동기 작업 호출
            #    (DB 트랜잭션이 커밋된 후에 Celery가 실행되도록 보장)
            transaction.on_commit(
                lambda: process_job_posting.delay(self.posting_id)
            )
    ```

-----

### \#\# 4단계: `Resume` 수집 파이프라인 개편 (AI 1회 사용)

이력서가 저장될 때 **AI를 딱 한 번만 호출**하여 "요약본"을 만들고, 이 요약본을 임베딩합니다.

1.  **모델 확장 (`app/job/models.py`):**

      * `Resume` 모델에 `experience_summary = models.TextField(null=True, blank=True, help_text="AI가 요약한 직무 경험")` 필드를 추가합니다.
      * `makemigrations` 및 `migrate` 실행.

2.  **Celery 작업 생성 (`app/job/tasks.py`):**

      * `@shared_task`로 `process_resume(user_id)` 함수를 만듭니다.
      * **작업 내용:**
        1.  `user_id`로 `Resume` 객체를 조회합니다.
        2.  `instance.needs_analysis()`를 확인하여(해시 비교) 분석이 불필요하면 `return`.
        3.  **[AI 호출 (1회)]** LLM(Gemini)을 호출하여 `content` 원본으로부터 `analysis_result` (JSON: 스킬, 경력)와 `experience_summary` (Text: 직무 역량 요약본)를 **동시에** 추출합니다.
        4.  이 결과(2개)를 `Resume` 객체에 업데이트하고 `save()`합니다. (이때 `save()`가 재귀 호출되지 않도록 `update_fields` 사용)
        5.  **[임베딩 개선]** `content` 원본 대신, 노이즈가 제거된 `experience_summary` 텍스트를 임베딩 벡터로 만듭니다.
        6.  `ChromaDB`의 'resumes' 컬렉션에 `user_id`와 벡터를 `upsert`합니다.

3.  **모델 수정 (`app/job/models.py`):**

      * `Resume` 모델의 `save()` 메소드를 오버라이드하여 시그널을 제거합니다.

    <!-- end list -->

    ```python
    # app/job/models.py
    from django.db import models, transaction
    from job.tasks import process_resume

    class Resume(models.Model):
        # ... (필드, content_hash, experience_summary 등) ...

        def save(self, *args, **kwargs):
            # (해시값 비교를 위한 복잡한 로직 대신,
            #  Celery 작업 내에서 needs_analysis()를 다시 호출하는 것이 더 안전할 수 있음)

            # (간단한 구현)
            # 1. 해시값 계산 및 저장 준비
            current_hash = self.calculate_hash()

            # (신규가 아니고, 해시가 동일하면 AI/임베딩 작업을 스킵할 수 있음)
            # (여기서는 단순화: `process_resume` 작업이 `needs_analysis`로 이중 체크)
            self.content_hash = current_hash

            # 2. DB에 일단 저장
            super().save(*args, **kwargs)

            # 3. 명시적으로 비동기 작업 호출
            transaction.on_commit(
                lambda: process_resume.delay(self.user_id)
            )
    ```

-----

### \#\# 5단계: 관리자 커맨드 개편 (명령자 역할)

`process_data.py`가 직접 임베딩을 수행하는 대신, 모든 객체의 **재-처리를 Celery에 지시**하는 "명령자" 역할로 변경합니다. (기존 데이터 마이그레이션용)

1.  **커맨드 수정 (`job/management/commands/process_data.py`):**
      * `process_job_postings` 함수:
          * `ChromaDB` 클라이언트 코드를 **제거**합니다.
          * `job_posting.save()` 대신, `process_job_posting.delay(job_posting.posting_id)`를 호출하도록 변경합니다.
      * `process_resumes` 함수:
          * `ChromaDB` 클라이언트 코드를 **제거**합니다.
          * `documents.append` 로직 대신, `process_resume.delay(resume.user_id)`를 호출하도록 변경합니다.

-----

### \#\# 6단계: 실시간 추천 엔진 구현 (AI-Free)

사용자의 추천 요청 시점에 CrewAI 대신 **DB 쿼리만으로** 결과를 생성하는 로직을 구현합니다.

1.  **추천 로직 생성 (`app/job/recommender.py`):**
      * `def get_recommendations(user_id: int) -> list[dict]:` 함수를 만듭니다.
      * **로직:**
        1.  `Resume`에서 `user_id`로 `analysis_result.skills` (JSON)를 가져옵니다.
        2.  `ChromaDB`('resumes')에서 `user_id`의 **이력서 벡터**를 가져옵니다.
        3.  `ChromaDB`('job\_postings')에 이력서 벡터로 `.query(n_results=50)`를 실행 -\> 50개 `posting_id` 획득. (의미론적 검색)
        4.  `Neo4j`에 50개 `posting_id`와 이력서 스킬(JSON)을 쿼리하여 스킬이 매칭되는 20개로 정제합니다. (하이브리드 검색)
        5.  **[규칙 기반 `match_reason` 생성]:** 20개 후보의 `JobPosting` 객체와 `Resume` 객체를 Python 코드로 비교하여 `match_reason` 문자열을 생성합니다. (예: "보유 스킬 [Python, Django] 일치. 3년 경력(요구 3년) 부합.")
        6.  `match_score`를 계산하고 정렬하여 최종 Top 10 리스트를 반환합니다.

-----

### \#\# 7단계: API 엔드포인트 교체 (최종)

사용자 요청을 받는 API 뷰가 더 이상 CrewAI를 호출하지 않도록 변경합니다.

1.  **API 뷰 수정 (`app/job/views.py`):**

      * `JobRecommendationViewSet` (또는 관련 뷰)를 수정합니다.
      * `agent/crew.py`의 `JobHunterCrew`를 호출하던 **모든 코드를 제거**합니다.
      * `job/recommender.py`의 `get_recommendations(request.user.id)`를 호출합니다.
      * 반환된 Top 10 JSON을 사용자에게 즉시(0.1초 내) 반환합니다.

2.  **`agent/` 앱 정리:**

      * `agent/crew.py`, `agent/agents.py`, `agent/tasks.py`에서 `JobHunter`, `job_posting_inspector` 등 추천 시점에 사용되던 에이전트/태스크 코드를 제거합니다. (3단계의 `resume_inspector` 로직만 `job/tasks.py`로 이동/통합)

# Job App

채용 공고 관리 앱

## 책임

- 채용 공고 CRUD
- 자동 스킬 추출
- 벡터 임베딩 생성
- Neo4j 그래프 업데이트

## 주요 컴포넌트

### Models
- `JobPosting`: 채용 공고 모델

### Services
- `JobService`: 비즈니스 로직
  - `get_job_posting()`: 공고 조회
  - `create_job_posting()`: 공고 생성
  - `update_job_posting()`: 공고 수정
  - `delete_job_posting()`: 공고 삭제
  - `process_job_posting_sync()`: 공고 처리 (스킬 추출, 임베딩)

### Tasks
- `process_job_posting`: Celery 비동기 작업

### API Endpoints
- `GET /api/v1/jobs/`: 목록
- `POST /api/v1/jobs/`: 생성
- `GET /api/v1/jobs/{id}/`: 조회
- `PUT /api/v1/jobs/{id}/`: 수정
- `DELETE /api/v1/jobs/{id}/`: 삭제

## 테스트

```bash
pytest app/job/tests/
```

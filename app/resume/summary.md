# Resume App

이력서 관리 및 분석 앱

## 책임

- 이력서 CRUD
- LLM 기반 이력서 분석
- 경력 연차 계산
- 핵심 강점 추출
- 벡터 임베딩 생성

## 주요 컴포넌트

### Models
- `Resume`: 이력서 모델

### Services
- `ResumeService`: 비즈니스 로직
  - `get_resume()`: 이력서 조회
  - `create_resume()`: 이력서 생성
  - `update_resume()`: 이력서 수정
  - `delete_resume()`: 이력서 삭제
  - `analyze_resume_with_llm()`: LLM 분석
  - `process_resume_sync()`: 이력서 처리

### Tasks
- `process_resume`: Celery 비동기 작업

### API Endpoints
- `GET /api/v1/resumes/`: 목록
- `POST /api/v1/resumes/`: 생성
- `GET /api/v1/resumes/{user_id}/`: 조회
- `PATCH /api/v1/resumes/{user_id}/`: 수정
- `DELETE /api/v1/resumes/{user_id}/`: 삭제

## 테스트

```bash
pytest app/resume/tests/
```

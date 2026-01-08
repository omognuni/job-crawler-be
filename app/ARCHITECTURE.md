## 목적
이 프로젝트는 “변경에 유연한 구조”를 목표로, 유스케이스 중심(Application) + 포트/어댑터(Ports/Adapters) 스타일로 정리합니다.

## 레이어 규칙(의존 방향)
- **views (Presentation)**: HTTP 처리만 담당. 비즈니스 로직/DB/외부 연동 금지.
- **application (UseCases)**: 오케스트레이션 담당. DB/Chroma/Neo4j/Gemini SDK 직접 import 금지(포트만 의존).
- **domain**: 순수 로직(점수 계산/정규화 등). Django/외부 I/O 금지.
- **common/adapters (Infrastructure)**: Django ORM, Chroma, Neo4j, Gemini 등 구체 구현.

의존 방향은 다음만 허용:

`views -> services(thin facade) -> application(usecases) -> ports -> adapters`

## DI(의존성 조립) 규칙
각 앱은 `application/container.py`에서 유스케이스를 조립합니다.
- 예: `resume.application.container.build_process_resume_usecase()`
- `tasks.py`, `services.py`, `views.py`는 container를 통해 유스케이스를 얻습니다.

## 테스트에서 부수효과 비활성
테스트에서는 모델 `save()`의 자동 처리(Celery 스케줄링)를 끕니다.
- 설정: `AUTO_PROCESS_RESUME_ON_SAVE`, `AUTO_PROCESS_JOB_ON_SAVE`
- `app/conftest.py`의 autouse fixture가 테스트에서 자동으로 False로 설정합니다.

## API 동작(중요 변경)
- `GET /api/v1/resumes/{id}/analyze/` 는 동기 응답이 아니라 **202 + task_id**를 반환합니다.
- 상태 확인: `GET /api/v1/resumes/{id}/analyze-status/`

## Request-ID(코릴레이션)
- 모든 요청은 `common.middleware.RequestIdMiddleware`를 통해 `X-Request-ID`가 응답에 포함됩니다.
- 로그에는 `request_id=...`가 기본으로 찍힙니다.

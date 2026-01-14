# GitHub Copilot Instructions (Job Crawler Backend)

## Single Source of Truth
- 이 레포의 개발 규칙/워크플로우는 **`.cursor/rules/`** 를 단일 소스로 관리합니다.
- Copilot은 코드/문서 변경 시 아래 규칙을 우선 준수해야 합니다:
  - `.cursor/rules/global.mdc`
  - `.cursor/rules/00_index.mdc`
  - 작업에 따라 `.cursor/rules/architecture.mdc`, `.cursor/rules/python_django.mdc`, `.cursor/rules/ticket.mdc`

## Key constraints (요약)
- 명령 실행: 컨테이너에서 `uv`
- 작업 전: `docker-compose.yml` 확인

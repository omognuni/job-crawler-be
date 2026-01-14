# Claude / AI Agent Instructions (Job Crawler Backend)

## Single Source of Truth
- 이 레포의 규칙은 **`.cursor/rules/`** 를 단일 소스로 관리합니다.
- Claude는 아래 문서를 **반드시 먼저 읽고 준수**합니다:
  - `.cursor/rules/global.mdc` (항상 적용)
  - `.cursor/rules/00_index.mdc` (규칙 인덱스)
  - 작업 성격에 따라 `.cursor/rules/architecture.mdc`, `.cursor/rules/python_django.mdc`, `.cursor/rules/ticket.mdc`

## 최소 준수사항(요약)
- 명령 실행은 **컨테이너에서 `uv` 사용**
- 작업 전 **`docker-compose.yml` 확인**
- 작업 시작 전 **Atlassian MCP로 Jira 티켓 확인(없으면 생성 기준 적용)**
- Markdown 문서 변경 시 **Confluence에 MCP로 반영**

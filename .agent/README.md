# .agent (Job Crawler Backend)

## Purpose
이 디렉토리는 특정 에이전트/IDE가 프로젝트 규칙을 찾을 때 사용할 수 있는 “진입점”으로 둡니다.

## Canonical Rules
- 이 레포의 규칙 단일 소스는 **`.cursor/rules/`** 입니다.
- 아래 파일을 우선으로 따르세요:
  - `.cursor/rules/global.mdc`
  - `.cursor/rules/00_index.mdc`

## Notes
- `.cursor/rules`와 본 문서가 충돌하면 **`.cursor/rules`가 우선**입니다.

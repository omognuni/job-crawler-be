## check-jira

너의 목표는 **FE/BE 관련 Jira 티켓을 확인**하고, **현재 변경사항을 근거로 상태를 자동 전환**하는 것이다.

### 입력(모호하면 질문)
- 사용자가 Jira 티켓 키(FE/BE)를 이미 알고 있으면 그대로 사용한다.
- 모르면 아래 자동 탐지로 후보 키를 수집한다. 그래도 없으면 사용자에게 티켓 키를 물어본다.

### 전체 절차(의사코드)
```text
REPOS = [
  { name: "BE", path: "/home/aa/workspace/job-crawler-be" },
  { name: "FE", path: "/home/aa/workspace/job-crawler-fe" },
]

1) Jira 접근 준비
   - Atlassian MCP 인증이 필요하다.
   - cloudId는 getAccessibleAtlassianResources로 가져온다.
   - 인증(401)이면: 사용자에게 "Atlassian 인증 필요" 안내 후, 티켓 키를 받아도
     상태 전환은 보류하고, 대신 변경사항 요약만 제공한다.

2) 각 repo별 변경사항 수집(git)
   - git -C <path> rev-parse --is-inside-work-tree 로 repo 여부 확인
   - branch = git -C <path> rev-parse --abbrev-ref HEAD
   - status = git -C <path> status --porcelain
   - diffStat = git -C <path> diff --stat
   - diffNames = git -C <path> diff --name-only
   - commits = git -C <path> log -30 --pretty=%s
   - (선택) unpushed = git -C <path> log --oneline --decorate --max-count=20 @{u}..HEAD
     * upstream 없으면 skip

3) Jira 티켓 키 자동 탐지
   - REGEX = /[A-Z][A-Z0-9]+-\d+/
   - candidates = (branch + commits + diffNames)에서 REGEX 매칭하여 dedupe
   - repo별로 후보를 분류하되, 최종적으로 (FE/BE) 대표 키 1개씩 고르는 게 목표
   - 후보가 여러 개면: 사용자에게 어떤 키를 대상으로 할지 확인 질문

4) 티켓 조회(각 후보 키)
   - getJiraIssue로 summary/description/status 등을 가져온다.
   - 작업 내용 판단을 위해 description/AC(있다면)/체크리스트/DoD를 요약한다.

5) 상태 판정(권장안) + 애매하면 질문
   - 판단 입력: (status porcelain, diffStat, unpushed 유무, 커밋 메시지, 파일 변경 범위)
   - 기본 규칙(보수적으로):
     A) 변경이 존재(status porcelain != empty OR diffStat not empty OR unpushed exists)
        -> "진행 중" 권장
     B) 변경이 없고(working tree clean) 주요 커밋이 있고, PR/리뷰 대상 정황(예: branch가 main이 아님)
        -> "검토중" 권장
     C) 변경이 없고, main/master에 있고, 해당 티켓 작업이 완료되었음을 강하게 시사(예: 티켓 본문에 완료 링크/머지 언급)
        -> "완료" 후보. 단, 확실치 않으면 사용자에게 확인 질문.

6) Jira 전환(Transition)
   - getTransitionsForJiraIssue로 가능한 전환 목록을 가져온다.
   - 목표 상태명 매칭은 "In Progress/진행/진행중", "In Review/Review/검토/검토중", "Done/완료"를
     우선순위로 느슨하게(fuzzy/contains) 매칭한다.
   - 매칭 실패 또는 다중 매칭이면: 사용자에게 "현재 워크플로우에서 어떤 상태로 옮길까요?" 질문
     + 전환 후보 목록을 제시한다.
   - 확정되면 transitionJiraIssue로 전환한다.

7) Jira 코멘트 남기기(가능하면)
   - 코멘트에는 아래를 포함:
     - repo별 변경 요약(diffStat, 주요 파일, 커밋 메시지 일부)
     - AC/DoD 충족 여부에 대한 근거(부족하면 무엇이 남았는지)
     - 전환한 상태와 이유(또는 보류한 이유)
```

### 출력 형식(권장)
- **FE 요약**: 브랜치 / 변경 파일 수 / diffStat / 최근 커밋 상위 3개
- **BE 요약**: 브랜치 / 변경 파일 수 / diffStat / 최근 커밋 상위 3개
- **티켓별 판정**: 권장 상태 + 근거 + 애매한 점(질문)
- **전환 결과**: 전환 성공/실패 + 실패 시 가능한 전환 목록

### 주의
- 상태를 "완료"로 바꾸는 건 보수적으로: 확실하지 않으면 반드시 사용자에게 확인한다.
- Atlassian 인증 실패(401)면: 전환/코멘트는 수행하지 말고, 변경사항/권장 상태만 제시한다.

# Job Crawler Backend

Django REST Framework 기반 채용 공고 분석 및 추천 시스템

## 필수 요구사항

### 1. Python 환경
- Python >= 3.12 (3.12 또는 3.13 권장, 3.14는 일부 패키지 미지원)
- uv (패키지 매니저)

### 2. 의존성 설치

```bash
# uv를 사용하는 경우
uv sync

# 또는 pip 사용
pip install -e .
```

### 3. 환경 변수 설정

배포 서버에 다음 환경 변수를 설정해야 합니다:

```bash
# Django 설정
export SECRET_KEY="your-secret-key"
export DEBUG=False
export ALLOWED_HOSTS="your-domain.com"

# LLM API Key (아래 중 하나만 설정)
export OPENAI_API_KEY="sk-..."           # OpenAI (GPT-4 등)
export ANTHROPIC_API_KEY="sk-ant-..."   # Anthropic (Claude)
export GOOGLE_API_KEY="..."             # Google (Gemini)
```

## 배포 시 필요한 것

### ✅ 필요한 것:
- Python 실행 환경
- pip/uv로 설치된 Python 패키지들
- 환경 변수로 설정된 API Key
- 인터넷 연결 (LLM API 호출용)

### ❌ 필요하지 않은 것:
- Claude Desktop, Gemini CLI 같은 별도 프로그램
- GPU, 로컬 LLM 모델
- Docker (선택사항)

## 구조 설명

```
배포 서버
  │
  ├── Django App (Python 코드)
  │     └── CrewAI (Python 라이브러리)
  │           └── HTTP 요청 →→→ 외부 LLM API 서버
  │
  └── PostgreSQL/MySQL (DB)
```

**CrewAI는 Python 패키지**이며, API Key를 통해 **외부 LLM 서버에 HTTP 요청**을 보냅니다.

## 실행 방법

```bash
# 개발 환경
python manage.py runserver

# 프로덕션 환경
gunicorn app.config.wsgi:application
```

## Agent 동작 방식

1. Django View에서 `JobHunterCrew` 인스턴스 생성
2. CrewAI가 LLM API 호출 (OpenAI/Anthropic/Google)
3. Agent가 Tool을 사용하여 Django ORM으로 DB 조회
4. 결과를 사용자에게 반환

**별도의 Agent 프로그램 설치 불필요 - Python 라이브러리로 모두 처리됩니다.**


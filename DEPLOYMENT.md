# 배포 가이드

이 문서는 GitHub Actions를 사용한 자동 배포 설정에 대한 가이드입니다.

## 🚀 배포 방식

### 자동 배포
- `main` 브랜치에 코드가 푸시될 때 자동으로 Docker 이미지를 빌드하고 레지스트리에 푸시합니다.

### 수동 배포
- GitHub Actions 탭에서 "Deploy to Production" 워크플로우를 수동으로 실행할 수 있습니다.
- **배포 대상 선택**: Docker Registry, SSH Server, AWS ECS, Google Cloud Run, Azure Container Instances
- **환경 선택**: production/staging
- **강제 배포**: 변경사항 없이도 배포 가능한 옵션

## 🎯 배포 대상별 설정

### 1. Docker Registry (기본값)
- Docker 이미지만 빌드하고 GitHub Container Registry에 푸시
- 실제 서버에서 수동으로 이미지를 풀하고 실행해야 함

### 2. SSH Server
- SSH를 통해 원격 서버에 직접 배포
- 자동으로 Docker Compose로 서비스 시작
- 헬스체크 자동 수행

### 3. 클라우드 플랫폼
- AWS ECS, Google Cloud Run, Azure Container Instances
- 각 플랫폼별 추가 설정 필요

## 🔐 GitHub Secrets 설정

배포를 위해 다음 GitHub Secrets를 설정해야 합니다:

### 공통 필수 Secrets

1. **SECRET_KEY**
   - Django SECRET_KEY 값
   - 예: `%2uwo2-7e8t-31n^0(ju-xdeg!y5c=kn1_fkxknz7uw8xs3-g$`

2. **ALLOWED_HOSTS**
   - 허용된 호스트 목록 (쉼표로 구분)
   - 예: `yourdomain.com,api.yourdomain.com`

3. **PORT**
   - 애플리케이션 포트 (기본값: 8000)
   - 예: `8000`

4. **DB_NAME**
   - 데이터베이스 이름
   - 예: `job_crawler`

5. **DB_PASS**
   - 데이터베이스 비밀번호
   - 예: `your_secure_password`

6. **DB_USER**
   - 데이터베이스 사용자명
   - 예: `postgres`

7. **OPENAI_API_KEY**
   - OpenAI API 키
   - 예: `sk-proj-...`

8. **GOOGLE_API_KEY**
   - Google API 키
   - 예: `AIzaSy...`

9. **GOOGLE_OAUTH_ENABLED**
   - Google OAuth 기능 플래그
   - `False`면 OAuth 엔드포인트가 404로 비활성화되어 롤백/세이프가드로 사용 가능
   - 예: `True`

10. **GOOGLE_OAUTH_CLIENT_ID**
   - Google OAuth Client ID
   - 예: `1234567890-xxxx.apps.googleusercontent.com`

11. **GOOGLE_OAUTH_CLIENT_SECRET**
   - Google OAuth Client Secret (절대 로그/응답에 노출 금지)
   - 예: `GOCSPX-...`

12. **GOOGLE_OAUTH_ALLOWED_REDIRECT_URIS**
   - 허용된 Redirect URI 화이트리스트(정확 일치, 쉼표로 구분)
   - 예: `https://your-frontend.com/auth/google/callback,https://staging.your-frontend.com/auth/google/callback`

13. **GOOGLE_OAUTH_STATE_TTL_SECONDS**
   - state/PKCE 유효기간(초)
   - 예: `600`

### SSH Server 배포용 추가 Secrets

14. **SSH_HOST**
   - SSH 서버 호스트명 또는 IP
   - 예: `your-server.com` 또는 `192.168.1.100`

15. **SSH_USERNAME**
    - SSH 사용자명
    - 예: `ubuntu` 또는 `root`

16. **SSH_PRIVATE_KEY**
    - SSH 개인키 (전체 내용)
    - 예: `-----BEGIN OPENSSH PRIVATE KEY-----...`

17. **SSH_PORT** (선택사항)
    - SSH 포트 (기본값: 22)
    - 예: `22`

### Secrets 설정 방법

1. GitHub 저장소로 이동
2. Settings → Secrets and variables → Actions
3. "New repository secret" 클릭
4. 위의 각 항목에 대해 이름과 값을 입력
5. "Add secret" 클릭

## 🐳 Docker 이미지

배포 시 GitHub Container Registry (ghcr.io)에 Docker 이미지가 자동으로 빌드되고 푸시됩니다.

- 이미지 태그: `ghcr.io/username/repository:latest`
- 캐시를 사용하여 빌드 속도 최적화

## 🔍 헬스체크

배포 후 자동으로 헬스체크가 수행됩니다:

- 엔드포인트: `GET /health/`
- 응답 예시:
  ```json
  {
    "status": "healthy",
    "message": "Service is running"
  }
  ```

## 📋 배포 프로세스

### Docker Registry 배포
1. **코드 푸시** → 자동으로 Docker 이미지 빌드 및 푸시
2. **수동 배포**: 서버에서 다음 명령어 실행
   ```bash
   docker pull ghcr.io/username/repository:latest
   docker-compose -f docker-compose.prod.yml up -d
   ```

### SSH Server 배포
1. **코드 푸시** 또는 **수동 트리거** (SSH Server 선택)
2. **Docker 이미지 빌드** 및 Container Registry에 푸시
3. **SSH를 통한 원격 배포**
   - 서버에 SSH 연결
   - 기존 컨테이너 중지
   - 최신 이미지 풀
   - Docker Compose로 새 컨테이너 시작
4. **헬스체크 자동 수행**
5. **배포 완료**

### 클라우드 플랫폼 배포
1. **코드 푸시** 또는 **수동 트리거** (해당 플랫폼 선택)
2. **Docker 이미지 빌드** 및 Container Registry에 푸시
3. **플랫폼별 추가 설정 필요**
   - AWS ECS: Task Definition 업데이트
   - Google Cloud Run: 서비스 설정
   - Azure Container Instances: 컨테이너 그룹 설정

## 🛠️ 로컬 테스트

배포 전 로컬에서 테스트하려면:

```bash
# 프로덕션 환경으로 로컬 테스트
docker-compose -f docker-compose.prod.yml up -d

# 헬스체크
curl http://localhost:8000/health/
```

## 🔧 문제 해결

### 배포 실패 시
1. GitHub Actions 로그 확인
2. Secrets 설정 확인
3. 서버 리소스 확인

### SSH 배포 실패 시
1. SSH 키 권한 확인 (`chmod 600 ~/.ssh/id_rsa`)
2. SSH 서버 접근 권한 확인
3. Docker 설치 및 실행 권한 확인

### 헬스체크 실패 시
1. 애플리케이션 로그 확인
2. 데이터베이스 연결 확인
3. 포트 충돌 확인

## 📝 주의사항

- 프로덕션 환경에서는 반드시 강력한 SECRET_KEY 사용
- 데이터베이스 비밀번호는 복잡하게 설정
- API 키는 정기적으로 로테이션
- SSH 키는 안전하게 보관
- 배포 전 충분한 테스트 수행

## 🚀 빠른 시작

## ✅ Google OAuth 운영 체크리스트 (SCRUM-29)

### Google Console 설정 체크리스트
- [ ] OAuth 동의 화면 구성(프로덕션 도메인/브랜딩/스코프 확인)
- [ ] OAuth Client 생성(Web Application)
- [ ] 승인된 Redirect URI에 FE 콜백 URL 등록(DEV/STG/PROD)
- [ ] (필요 시) 승인된 JavaScript origin 등록
- [ ] 배포 환경별 `client_id/client_secret` 안전하게 저장(Secrets)

### 운영 QA 체크리스트
- [ ] **플래그 OFF**(`GOOGLE_OAUTH_ENABLED=False`) 시:
  - [ ] `/api/v1/users/oauth/google/start/` 404
  - [ ] `/api/v1/users/oauth/google/callback/` 404
- [ ] **플래그 ON**(`GOOGLE_OAUTH_ENABLED=True`) 시:
  - [ ] 정상 로그인 성공(redirect → code/state → callback → JWT 발급)
  - [ ] 사용자 취소/실패 케이스에서 FE/BE가 기대한 에러 코드로 처리되는지 확인
  - [ ] state mismatch/만료/재사용이 안전하게 실패하는지 확인
  - [ ] 토큰/PII가 로그/응답에 노출되지 않는지 확인(마스킹/세부사유 미노출)

### 롤백 플랜
- [ ] 문제가 발생하면 `GOOGLE_OAUTH_ENABLED=False`로 즉시 비활성화(기존 로그인 유지)

### 1. Docker Registry 배포 (가장 간단)
1. GitHub Secrets 설정 (공통 필수 Secrets만)
2. `main` 브랜치에 코드 푸시
3. 서버에서 수동으로 이미지 풀 및 실행

### 2. SSH Server 배포 (자동화)
1. GitHub Secrets 설정 (공통 + SSH Secrets)
2. SSH 서버에 Docker 설치
3. `main` 브랜치에 코드 푸시 또는 수동 배포 실행

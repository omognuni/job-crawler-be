# 배포 가이드

이 문서는 GitHub Actions를 사용한 자동 배포 설정에 대한 가이드입니다.

## 🚀 배포 방식

### 자동 배포
- `main` 브랜치에 코드가 푸시될 때 자동으로 배포됩니다.

### 수동 배포
- GitHub Actions 탭에서 "Deploy to Production" 워크플로우를 수동으로 실행할 수 있습니다.
- 환경 선택 (production/staging) 및 강제 배포 옵션을 제공합니다.

## 🔐 GitHub Secrets 설정

배포를 위해 다음 GitHub Secrets를 설정해야 합니다:

### 필수 Secrets

1. **SECRET_KEY**
   - Django SECRET_KEY 값
   - 예: `%2uwo2-7e8t-31n^0(ju-xdeg!y5c=kn1_fkxknz7uw8xs3-g$`

2. **ALLOWED_HOSTS**
   - 허용된 호스트 목록 (쉼표로 구분)
   - 예: `yourdomain.com,api.yourdomain.com`

3. **DB_NAME**
   - 데이터베이스 이름
   - 예: `job_crawler`

4. **DB_PASS**
   - 데이터베이스 비밀번호
   - 예: `your_secure_password`

5. **DB_USER**
   - 데이터베이스 사용자명
   - 예: `postgres`

6. **OPENAI_API_KEY**
   - OpenAI API 키
   - 예: `sk-proj-...`

7. **GOOGLE_API_KEY**
   - Google API 키
   - 예: `AIzaSy...`

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

1. **코드 푸시** 또는 **수동 트리거**
2. **Docker 이미지 빌드** 및 Container Registry에 푸시
3. **프로덕션 서버에 배포**
   - 기존 컨테이너 중지
   - 최신 이미지로 새 컨테이너 시작
4. **헬스체크 수행**
5. **배포 완료**

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

### 헬스체크 실패 시
1. 애플리케이션 로그 확인
2. 데이터베이스 연결 확인
3. 포트 충돌 확인

## 📝 주의사항

- 프로덕션 환경에서는 반드시 강력한 SECRET_KEY 사용
- 데이터베이스 비밀번호는 복잡하게 설정
- API 키는 정기적으로 로테이션
- 배포 전 충분한 테스트 수행

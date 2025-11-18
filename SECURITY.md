# 보안 가이드

## 보안 감사 완료 (2025-11-17)

### ✅ 수정된 보안 이슈

#### 🔴 심각 (Critical) - 수정 완료
1. **하드코딩된 Neo4j 비밀번호**
   - 위치: `app/common/graph_db.py`, `docker-compose.prod.yml`
   - 수정: 환경 변수로 이동 (`NEO4J_PASSWORD`)
   - 설정: `app/config/settings.py`에 검증 로직 추가

2. **SECRET_KEY를 API 인증에 직접 사용**
   - 위치: `app/job/permissions.py`
   - 수정: 별도의 `API_SECRET_KEY` 생성 및 사용
   - 보안: Django SECRET_KEY와 API 인증 키 분리

3. **DEBUG 모드 기본값**
   - 수정 전: `DEBUG=True` (기본값)
   - 수정 후: `DEBUG=False` (기본값)
   - 프로덕션 배포 시 안전

#### 🟡 경고 (Warning) - 수정 완료
4. **기본 SECRET_KEY 값**
   - 수정: 환경 변수 필수로 변경
   - 미설정 시 `ValueError` 발생

5. **보안 헤더 미설정**
   - 추가: XSS 필터, Content-Type Nosniff, X-Frame-Options
   - 추가: CORS 설정 (django-cors-headers)
   - 추가: HSTS, Secure Cookie (프로덕션)

6. **비밀번호 정책**
   - 최소 8자 이상
   - 숫자/문자 혼합 필수
   - Django의 기본 검증 활용

#### 🐳 Docker 보안 개선
7. **Non-root 사용자**
   - Dockerfile에 `appuser` 추가
   - 컨테이너 내 권한 최소화

### 📋 필수 환경 변수

프로덕션 배포 전 다음 환경 변수를 반드시 설정하세요:

```bash
# 필수 (미설정 시 서버 시작 실패)
SECRET_KEY=                # Django 암호화 키
API_SECRET_KEY=            # API 인증 키
NEO4J_PASSWORD=            # Neo4j 데이터베이스 비밀번호

# 권장
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
DB_PASS=secure-password
GOOGLE_API_KEY=your-key
CORS_ALLOWED_ORIGINS=https://yourdomain.com
```

`.env.prod.example` 파일을 참조하여 `.env.prod` 파일을 생성하세요.

### 🔒 보안 설정 요약

#### 인증 & 권한
- ✅ JWT 기반 인증 (djangorestframework-simplejwt)
- ✅ API 키 검증 (별도의 API_SECRET_KEY)
- ✅ 비밀번호 복잡도 검증
- ✅ Django 기본 비밀번호 검증 활용

#### 데이터 보호
- ✅ Django ORM 사용 (SQL 인젝션 방지)
- ✅ Neo4j 파라미터화 쿼리 (Cypher 인젝션 방지)
- ✅ 환경 변수를 통한 민감 정보 관리
- ✅ .gitignore에 .env 파일 등록

#### 네트워크 보안
- ✅ CORS 설정 (화이트리스트 기반)
- ✅ HTTPS 리다이렉트 (프로덕션)
- ✅ Secure Cookie 설정
- ✅ HSTS 헤더 (프로덕션)

#### 보안 헤더
- ✅ XSS 필터 활성화
- ✅ Content-Type Nosniff
- ✅ X-Frame-Options: DENY
- ✅ CSRF 보호

### ⚠️ 추가 권장 사항

#### 1. Rate Limiting
현재 Rate Limiting이 구현되지 않았습니다. 프로덕션 환경에서는 다음을 권장합니다:
- django-ratelimit 또는 django-throttle-requests 사용
- API 엔드포인트별 요청 제한 설정

```python
# 예시
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='100/h')
def my_view(request):
    pass
```

#### 2. 로깅 및 모니터링
- 인증 실패 로그
- 비정상적인 API 요청 패턴 감지
- 보안 이벤트 알림

#### 3. 정기 보안 점검
- 의존성 취약점 스캔: `pip-audit` 또는 `safety`
- 코드 정적 분석: `bandit`
- 컨테이너 이미지 스캔: `trivy` 또는 `clair`

```bash
# 의존성 취약점 검사
pip install pip-audit
pip-audit

# 코드 보안 스캔
pip install bandit
bandit -r app/
```

#### 4. 백업 및 재해 복구
- 정기 데이터베이스 백업
- 백업 데이터 암호화
- 복구 절차 문서화 및 테스트

#### 5. 접근 제어
- PostgreSQL: 외부 접근 차단 (내부 네트워크만)
- Neo4j: 브라우저 접근 제한
- Redis: 비밀번호 설정 권장

### 🔍 보안 체크리스트

#### 배포 전
- [ ] `.env.prod` 파일 생성 및 모든 필수 환경 변수 설정
- [ ] SECRET_KEY 및 API_SECRET_KEY를 강력한 랜덤 문자열로 생성
- [ ] 모든 데이터베이스 비밀번호를 안전한 값으로 변경
- [ ] ALLOWED_HOSTS에 실제 도메인 추가
- [ ] CORS_ALLOWED_ORIGINS에 프론트엔드 도메인 추가
- [ ] DEBUG=False 확인
- [ ] HTTPS 인증서 설정 (Let's Encrypt 등)

#### 배포 후
- [ ] 보안 헤더 응답 확인 (https://securityheaders.com)
- [ ] SSL/TLS 설정 테스트 (https://www.ssllabs.com)
- [ ] 의존성 취약점 스캔
- [ ] 침투 테스트 (가능한 경우)

### 📞 보안 이슈 보고

보안 취약점을 발견한 경우, 공개 이슈 트래커 대신 프로젝트 관리자에게 직접 연락하세요.

---

**최종 업데이트**: 2025-11-17
**감사자**: AI Security Agent
**상태**: ✅ 보안 감사 완료

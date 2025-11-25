# Frontend Developer Guide - Job Crawler API

이 문서는 Job Crawler Backend API를 프론트엔드에서 사용하기 위한 핵심 정보를 담고 있습니다.

## 📋 목차

1. [기본 정보](#기본-정보)
2. [인증 (Authentication)](#인증-authentication)
3. [API 엔드포인트](#api-엔드포인트)
4. [데이터 모델](#데이터-모델)
5. [에러 처리](#에러-처리)
6. [CORS 설정](#cors-설정)

---

## 기본 정보

### Base URL
```
프로덕션: https://your-domain.com
로컬 개발: http://localhost:8000
```

### API 버전
- 현재 버전: `v1`
- 모든 API 경로는 `/api/v1/` 로 시작합니다

### API 문서
- **Swagger UI**: `/api/v1/schema/swagger-ui/`
- **ReDoc**: `/api/v1/schema/redoc/`
- **OpenAPI Schema**: `/api/v1/schema/`

### Health Check
```http
GET /health/
```

**응답 예시:**
```json
{
  "status": "healthy",
  "message": "Service is running"
}
```

---

## 인증 (Authentication)

### 1. API Key 인증 (기본)

모든 API 요청에는 `X-Api-Key` 헤더가 필요합니다.

```javascript
const headers = {
  'X-Api-Key': 'YOUR_API_SECRET_KEY',
  'Content-Type': 'application/json'
};
```

> ⚠️ **중요**: API Secret Key는 백엔드 관리자에게 문의하세요.

### 2. JWT 인증 (사용자 인증)

사용자별 데이터 접근 시 JWT 토큰을 사용합니다.

#### 회원가입
```http
POST /api/v1/users/register/
```

**요청 본문:**
```json
{
  "username": "user123",
  "email": "user@example.com",
  "password": "secure_password123"
}
```

**응답:**
```json
{
  "username": "user123",
  "email": "user@example.com"
}
```

#### 로그인 및 토큰 발급
```http
POST /api/v1/users/login/
```

**요청 본문:**
```json
{
  "username": "user123",
  "password": "secure_password123"
}
```

**응답:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

#### 토큰 리프레시
```http
POST /api/v1/users/token/refresh/
```

**요청 본문:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**응답:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

#### JWT 토큰 사용
```javascript
const headers = {
  'X-Api-Key': 'YOUR_API_SECRET_KEY',
  'Authorization': 'Bearer ' + accessToken,
  'Content-Type': 'application/json'
};
```

> 📝 **토큰 유효기간**:
> - Access Token: 5분
> - Refresh Token: 1일

---

## API 엔드포인트

### 1. 채용 공고 (Job Postings)

Base Path: `/api/v1/jobs/`

#### 공고 목록 조회
```http
GET /api/v1/jobs/
```

**쿼리 파라미터:**
- `page`: 페이지 번호 (기본: 1)
- `page_size`: 페이지당 개수 (기본: 20)

**응답 예시:**
```json
{
  "count": 100,
  "next": "http://localhost:8000/api/v1/jobs/?page=2",
  "previous": null,
  "results": [
    {
      "posting_id": 1,
      "url": "https://www.wanted.co.kr/...",
      "company_name": "테크컴퍼니",
      "position": "백엔드 개발자",
      "main_tasks": "서버 개발 및 유지보수",
      "requirements": "Python, Django 경력 3년 이상",
      "preferred_points": "AWS 경험자 우대",
      "location": "서울",
      "district": "강남구",
      "employment_type": "정규직",
      "career_min": 3,
      "career_max": 7,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### 단일 공고 조회
```http
GET /api/v1/jobs/{posting_id}/
```

**응답:** 위 공고 객체와 동일

---

### 2. 이력서 (Resumes)

Base Path: `/api/v1/resumes/`

#### 내 이력서 조회
```http
GET /api/v1/resumes/{user_id}/
```

**응답 예시:**
```json
{
  "user_id": 1,
  "content": "경력 3년차 백엔드 개발자...",
  "analysis_result": {
    "skills": ["Python", "Django", "PostgreSQL"],
    "career_years": 3,
    "strengths": "REST API 설계 및 성능 최적화 경험"
  },
  "experience_summary": "3년차 백엔드 개발자로 Python, Django 기반의 API 서버 개발 경험",
  "analyzed_at": "2024-01-01T00:00:00Z",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### 이력서 생성/업데이트
```http
POST /api/v1/resumes/
PUT /api/v1/resumes/{user_id}/
```

**요청 본문:**
```json
{
  "user_id": 1,
  "content": "경력 3년차 백엔드 개발자입니다..."
}
```

---

### 3. 추천 (Recommendations)

Base Path: `/api/v1/recommendations/`

#### 내 추천 공고 목록
```http
GET /api/v1/recommendations/?user_id={user_id}
```

**응답 예시:**
```json
[
  {
    "id": 1,
    "user_id": 1,
    "job_posting": {
      "posting_id": 1,
      "company_name": "테크컴퍼니",
      "position": "백엔드 개발자",
      "url": "https://www.wanted.co.kr/...",
      "location": "서울",
      "employment_type": "정규직"
    },
    "rank": 1,
    "match_score": 85.5,
    "match_reason": "필수 스킬 3/4개 보유 | 우대사항 2개 충족 | 경력 요건 충족 (3년)",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

---

### 4. 검색 (Search)

Base Path: `/api/v1/search/`

#### 벡터 유사도 검색
```http
GET /api/v1/search/?query={검색어}&limit={개수}
```

**쿼리 파라미터:**
- `query` (필수): 검색 쿼리 텍스트
- `limit` (선택): 결과 개수 (기본: 20)

**응답 예시:**
```json
{
  "count": 10,
  "results": [
    {
      "posting_id": 1,
      "company_name": "테크컴퍼니",
      "position": "백엔드 개발자",
      "similarity_score": 0.89
    }
  ]
}
```

#### 하이브리드 검색 (Vector + Graph)
```http
POST /api/v1/search/hybrid/
```

**요청 본문:**
```json
{
  "query": "Django 백엔드 개발자",
  "skills": ["Python", "Django", "PostgreSQL"],
  "limit": 20
}
```

**응답 예시:**
```json
{
  "query": "Django 백엔드 개발자",
  "skills": ["Python", "Django", "PostgreSQL"],
  "count": 15,
  "results": [
    {
      "posting_id": 1,
      "company_name": "테크컴퍼니",
      "position": "백엔드 개발자",
      "matched_skills": ["Python", "Django"],
      "similarity_score": 0.89
    }
  ]
}
```

---

## 데이터 모델

### JobPosting (채용 공고)
```typescript
interface JobPosting {
  posting_id: number;
  url: string;
  company_name: string;
  position: string;
  main_tasks: string;
  requirements: string;
  preferred_points: string;
  location: string;
  district: string;
  employment_type: string;
  career_min: number;
  career_max: number;
  created_at: string;  // ISO 8601 datetime
  updated_at: string;  // ISO 8601 datetime
}
```

### Resume (이력서)
```typescript
interface Resume {
  user_id: number;
  content: string;
  analysis_result: {
    skills: string[];
    career_years: number;
    strengths: string;
  };
  experience_summary: string;
  analyzed_at: string;  // ISO 8601 datetime
  created_at: string;   // ISO 8601 datetime
  updated_at: string;   // ISO 8601 datetime
}
```

### JobRecommendation (추천)
```typescript
interface JobRecommendation {
  id: number;
  user_id: number;
  job_posting: JobPosting;
  rank: number;           // 추천 순위 (1-10)
  match_score: number;    // 매칭 점수 (0-100)
  match_reason: string;   // 추천 이유
  created_at: string;     // ISO 8601 datetime
}
```

---

## 에러 처리

### HTTP 상태 코드

| 코드 | 의미 | 설명 |
|------|------|------|
| 200 | OK | 성공 |
| 201 | Created | 리소스 생성 성공 |
| 400 | Bad Request | 잘못된 요청 (유효성 검사 실패) |
| 401 | Unauthorized | 인증 실패 (토큰 없음/만료) |
| 403 | Forbidden | 권한 없음 (API Key 없음/잘못됨) |
| 404 | Not Found | 리소스 없음 |
| 500 | Internal Server Error | 서버 오류 |

### 에러 응답 형식
```json
{
  "error": "Error message here",
  "detail": "Detailed explanation"
}
```

### 에러 처리 예제 (JavaScript)
```javascript
async function fetchJobPostings() {
  try {
    const response = await fetch('http://localhost:8000/api/v1/jobs/', {
      headers: {
        'X-Api-Key': 'YOUR_API_SECRET_KEY',
        'Authorization': 'Bearer ' + accessToken
      }
    });

    if (!response.ok) {
      if (response.status === 401) {
        // 토큰 만료 - 리프레시 필요
        await refreshToken();
        return fetchJobPostings(); // 재시도
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching job postings:', error);
    throw error;
  }
}
```

---

## CORS 설정

### 허용된 Origin
백엔드 관리자에게 프론트엔드 도메인 등록을 요청하세요.

### 허용된 헤더
- `accept`
- `accept-encoding`
- `authorization`
- `content-type`
- `x-api-key`
- `x-csrftoken`
- `x-requested-with`

### 자격 증명 포함
쿠키 및 인증 정보를 포함한 요청이 허용됩니다.

```javascript
fetch(url, {
  credentials: 'include',  // 쿠키 포함
  headers: {
    'X-Api-Key': 'YOUR_API_SECRET_KEY'
  }
});
```

---

## 사용 예제

### React + Axios 예제

```javascript
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';
const API_SECRET_KEY = 'YOUR_API_SECRET_KEY';

// Axios 인스턴스 생성
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'X-Api-Key': API_SECRET_KEY,
    'Content-Type': 'application/json'
  }
});

// JWT 토큰 인터셉터
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 채용 공고 목록 조회
export const getJobPostings = async (page = 1, pageSize = 20) => {
  const response = await apiClient.get('/jobs/', {
    params: { page, page_size: pageSize }
  });
  return response.data;
};

// 내 추천 공고 조회
export const getMyRecommendations = async (userId) => {
  const response = await apiClient.get('/recommendations/', {
    params: { user_id: userId }
  });
  return response.data;
};

// 이력서 업데이트
export const updateResume = async (userId, content) => {
  const response = await apiClient.put(`/resumes/${userId}/`, {
    user_id: userId,
    content: content
  });
  return response.data;
};

// 검색
export const searchJobs = async (query, limit = 20) => {
  const response = await apiClient.get('/search/', {
    params: { query, limit }
  });
  return response.data;
};
```

---

## 추가 정보

### 타임존
- 모든 datetime 필드는 **Asia/Seoul (KST)** 타임존 기준입니다
- ISO 8601 형식 사용: `2024-01-01T00:00:00Z`

### 페이지네이션
- 기본 페이지 크기: 20
- 최대 페이지 크기: 100
- 페이지네이션된 응답 형식:
  ```json
  {
    "count": 100,
    "next": "url_to_next_page",
    "previous": "url_to_previous_page",
    "results": [...]
  }
  ```

### 레이트 리미팅
현재는 레이트 리미팅이 적용되지 않았으나, 향후 추가될 수 있습니다.

---

## 문의

API 사용 중 문제가 발생하거나 질문이 있으면 백엔드 팀에 문의하세요.

- API Key 발급 요청
- CORS Origin 등록 요청
- API 스펙 관련 질문

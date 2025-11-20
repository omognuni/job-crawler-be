# Recommendation App

AI-Free 하이브리드 추천 시스템

## 책임

- 실시간 추천 생성
- 하이브리드 검색 (Vector + Graph)
- 매칭 점수 계산
- 추천 저장 및 관리

## 추천 알고리즘

### 3단계 하이브리드 추천

1. **Vector Search** (ChromaDB)
   - 이력서 임베딩 vs 채용 공고 임베딩
   - 50개 후보 선정

2. **Skill Matching** (Neo4j)
   - 사용자 스킬 vs 공고 필수 스킬
   - 20개로 정제

3. **Score Calculation**
   - 필수 스킬: 50점
   - 우대 사항: 30점
   - 경력 범위: 20점
   - **Total: 100점**

## 주요 컴포넌트

### Services
- `RecommendationService`: 추천 엔진
  - `get_recommendations()`: 실시간 추천 생성
  - `_filter_by_skill_graph()`: 스킬 기반 필터링
  - `_calculate_match_score_and_reason()`: 점수 계산
  - `get_skill_statistics()`: 스킬 통계

### API Endpoints
- `GET /api/v1/recommendations/`: 저장된 추천
- `GET /api/v1/recommendations/for-user/{user_id}/`: 실시간 추천
- `POST /api/v1/recommendations/`: 추천 저장
- `DELETE /api/v1/recommendations/{id}/`: 추천 삭제

## 성능

- **목표**: < 500ms (p95)
- **실제**: ~300-400ms

## 테스트

```bash
pytest app/recommendation/tests/
pytest app/tests/performance/  # 성능 테스트
```

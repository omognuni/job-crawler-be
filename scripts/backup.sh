#!/bin/bash
# Job Crawler Backend - 백업 스크립트
# Phase 2 시작 전 전체 시스템 백업

set -e  # 에러 발생 시 즉시 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 백업 디렉토리 생성
BACKUP_DIR="./backups/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Job Crawler Backend 백업 시작${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "백업 디렉토리: $BACKUP_DIR"
echo ""

# 1. PostgreSQL 백업
echo -e "${YELLOW}[1/5] PostgreSQL 백업 중...${NC}"
docker exec db pg_dump -U postgres crawler > "$BACKUP_DIR/postgres.sql" 2>/dev/null
if [ $? -eq 0 ]; then
    SIZE=$(du -h "$BACKUP_DIR/postgres.sql" | cut -f1)
    echo -e "${GREEN}✓ PostgreSQL 백업 완료 (크기: $SIZE)${NC}"
else
    echo -e "${RED}✗ PostgreSQL 백업 실패${NC}"
    exit 1
fi

# 2. Neo4j 백업
echo -e "${YELLOW}[2/5] Neo4j 백업 중...${NC}"
# Neo4j는 컨테이너 내부에서 백업 후 복사
docker exec job-crawler-be-neo4j-1 neo4j-admin database dump neo4j --to-path=/tmp 2>/dev/null || true
docker cp job-crawler-be-neo4j-1:/tmp/neo4j.dump "$BACKUP_DIR/neo4j.dump" 2>/dev/null || true
if [ -f "$BACKUP_DIR/neo4j.dump" ]; then
    SIZE=$(du -h "$BACKUP_DIR/neo4j.dump" | cut -f1)
    echo -e "${GREEN}✓ Neo4j 백업 완료 (크기: $SIZE)${NC}"
else
    echo -e "${YELLOW}⚠ Neo4j 백업 실패 (계속 진행)${NC}"
fi

# 3. ChromaDB 백업
echo -e "${YELLOW}[3/5] ChromaDB 백업 중...${NC}"
docker exec job-crawler-be-chromadb-1 tar -czf /tmp/chroma-backup.tar.gz /chroma 2>/dev/null || true
docker cp job-crawler-be-chromadb-1:/tmp/chroma-backup.tar.gz "$BACKUP_DIR/chroma.tar.gz" 2>/dev/null || true
if [ -f "$BACKUP_DIR/chroma.tar.gz" ]; then
    SIZE=$(du -h "$BACKUP_DIR/chroma.tar.gz" | cut -f1)
    echo -e "${GREEN}✓ ChromaDB 백업 완료 (크기: $SIZE)${NC}"
else
    echo -e "${YELLOW}⚠ ChromaDB 백업 실패 (계속 진행)${NC}"
fi

# 4. Redis 백업
echo -e "${YELLOW}[4/5] Redis 백업 중...${NC}"
docker exec redis redis-cli SAVE > /dev/null 2>&1 || true
docker cp redis:/data/dump.rdb "$BACKUP_DIR/redis.rdb" 2>/dev/null || true
if [ -f "$BACKUP_DIR/redis.rdb" ]; then
    SIZE=$(du -h "$BACKUP_DIR/redis.rdb" | cut -f1)
    echo -e "${GREEN}✓ Redis 백업 완료 (크기: $SIZE)${NC}"
else
    echo -e "${YELLOW}⚠ Redis 백업 실패 (계속 진행)${NC}"
fi

# 5. 코드 백업 (Git tag)
echo -e "${YELLOW}[5/5] Git 태그 생성 중...${NC}"
TAG_NAME="backup-$(date +%Y%m%d-%H%M%S)"
git tag -a "$TAG_NAME" -m "Backup before Phase 2 migration - $(date)" 2>/dev/null || true
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Git 태그 생성 완료: $TAG_NAME${NC}"
    echo -e "${YELLOW}  (push하려면: git push origin $TAG_NAME)${NC}"
else
    echo -e "${YELLOW}⚠ Git 태그 생성 실패 (계속 진행)${NC}"
fi

# 백업 메타데이터 생성
echo ""
echo -e "${YELLOW}백업 메타데이터 생성 중...${NC}"
cat > "$BACKUP_DIR/backup_info.txt" <<EOF
Job Crawler Backend 백업 정보
========================================
백업 일시: $(date)
백업 경로: $BACKUP_DIR

파일 목록:
$(ls -lh "$BACKUP_DIR" | tail -n +2)

체크섬:
$(md5sum "$BACKUP_DIR"/*.sql "$BACKUP_DIR"/*.dump "$BACKUP_DIR"/*.tar.gz "$BACKUP_DIR"/*.rdb 2>/dev/null || echo "체크섬 계산 불가")

데이터베이스 통계:
- PostgreSQL 테이블 수: $(docker exec db psql -U postgres -d crawler -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | xargs)
- 채용공고 수: $(docker exec db psql -U postgres -d crawler -t -c "SELECT COUNT(*) FROM agent_job_posting;" 2>/dev/null | xargs)
- 이력서 수: $(docker exec db psql -U postgres -d crawler -t -c "SELECT COUNT(*) FROM agent_resume;" 2>/dev/null | xargs)
- 추천 수: $(docker exec db psql -U postgres -d crawler -t -c "SELECT COUNT(*) FROM agent_job_recommendation;" 2>/dev/null | xargs)

Git 정보:
- 현재 브랜치: $(git branch --show-current 2>/dev/null || echo "N/A")
- 최근 커밋: $(git log -1 --oneline 2>/dev/null || echo "N/A")
- Git 태그: $TAG_NAME
EOF

echo -e "${GREEN}✓ 백업 메타데이터 생성 완료${NC}"

# 백업 디렉토리 크기 확인
echo ""
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}백업 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo "총 백업 크기: $TOTAL_SIZE"
echo "백업 위치: $BACKUP_DIR"
echo ""
echo -e "${YELLOW}백업 파일 확인:${NC}"
ls -lh "$BACKUP_DIR"
echo ""
echo -e "${GREEN}✓ 백업이 안전하게 완료되었습니다.${NC}"
echo -e "${YELLOW}⚠ 백업 파일을 안전한 외부 저장소에 복사하세요.${NC}"

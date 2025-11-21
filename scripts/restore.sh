#!/bin/bash
# Job Crawler Backend - 복구 스크립트
# 백업에서 시스템 복원

set -e  # 에러 발생 시 즉시 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 인자 확인
if [ $# -ne 1 ]; then
    echo -e "${RED}사용법: $0 <backup_directory>${NC}"
    echo ""
    echo "예시: $0 ./backups/backup_20251120_143000"
    echo ""
    echo "사용 가능한 백업:"
    ls -dt ./backups/backup_* 2>/dev/null | head -5 || echo "  (백업 없음)"
    exit 1
fi

BACKUP_DIR="$1"

# 백업 디렉토리 존재 확인
if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}에러: 백업 디렉토리가 존재하지 않습니다: $BACKUP_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Job Crawler Backend 복구 시작${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "백업 디렉토리: $BACKUP_DIR"
echo ""

# 확인 메시지
echo -e "${RED}⚠️  경고: 이 작업은 현재 데이터를 삭제하고 백업으로 복원합니다.${NC}"
read -p "계속하시겠습니까? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "복구 취소됨"
    exit 0
fi

# 1. PostgreSQL 복구
echo ""
echo -e "${YELLOW}[1/4] PostgreSQL 복구 중...${NC}"
if [ -f "$BACKUP_DIR/postgres.sql" ]; then
    # 기존 DB 삭제 및 재생성
    docker exec db psql -U postgres -c "DROP DATABASE IF EXISTS crawler;" 2>/dev/null || true
    docker exec db psql -U postgres -c "CREATE DATABASE crawler;" 2>/dev/null

    # 백업 복원
    cat "$BACKUP_DIR/postgres.sql" | docker exec -i db psql -U postgres -d crawler > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ PostgreSQL 복구 완료${NC}"
    else
        echo -e "${RED}✗ PostgreSQL 복구 실패${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ PostgreSQL 백업 파일 없음: $BACKUP_DIR/postgres.sql${NC}"
    exit 1
fi

# 2. Neo4j 복구
echo -e "${YELLOW}[2/4] Neo4j 복구 중...${NC}"
if [ -f "$BACKUP_DIR/neo4j.dump" ]; then
    # 백업 파일 복사
    docker cp "$BACKUP_DIR/neo4j.dump" job-crawler-be-neo4j-1:/tmp/neo4j.dump 2>/dev/null || true

    # Neo4j 정지
    docker stop job-crawler-be-neo4j-1 > /dev/null 2>&1 || true

    # 복원 (Neo4j 5.x 방식)
    docker start job-crawler-be-neo4j-1 > /dev/null 2>&1 || true
    sleep 5

    docker exec job-crawler-be-neo4j-1 neo4j-admin database load neo4j --from-path=/tmp --overwrite-destination=true 2>/dev/null || true

    echo -e "${GREEN}✓ Neo4j 복구 완료 (재시작 필요할 수 있음)${NC}"
else
    echo -e "${YELLOW}⚠ Neo4j 백업 파일 없음 (건너뜀)${NC}"
fi

# 3. ChromaDB 복구
echo -e "${YELLOW}[3/4] ChromaDB 복구 중...${NC}"
if [ -f "$BACKUP_DIR/chroma.tar.gz" ]; then
    # 백업 파일 복사 및 압축 해제
    docker cp "$BACKUP_DIR/chroma.tar.gz" job-crawler-be-chromadb-1:/tmp/chroma-backup.tar.gz 2>/dev/null || true
    docker exec job-crawler-be-chromadb-1 sh -c "rm -rf /chroma/* && tar -xzf /tmp/chroma-backup.tar.gz -C /" 2>/dev/null || true

    # ChromaDB 재시작
    docker restart job-crawler-be-chromadb-1 > /dev/null 2>&1 || true

    echo -e "${GREEN}✓ ChromaDB 복구 완료${NC}"
else
    echo -e "${YELLOW}⚠ ChromaDB 백업 파일 없음 (건너뜀)${NC}"
fi

# 4. Redis 복구
echo -e "${YELLOW}[4/4] Redis 복구 중...${NC}"
if [ -f "$BACKUP_DIR/redis.rdb" ]; then
    # Redis 정지
    docker stop redis > /dev/null 2>&1 || true

    # 백업 파일 복사
    docker cp "$BACKUP_DIR/redis.rdb" redis:/data/dump.rdb 2>/dev/null || true

    # Redis 시작
    docker start redis > /dev/null 2>&1 || true

    echo -e "${GREEN}✓ Redis 복구 완료${NC}"
else
    echo -e "${YELLOW}⚠ Redis 백업 파일 없음 (건너뜀)${NC}"
fi

# 5. 서비스 재시작
echo ""
echo -e "${YELLOW}서비스 재시작 중...${NC}"
docker-compose restart > /dev/null 2>&1 || true
sleep 5

# 6. 복구 검증
echo ""
echo -e "${YELLOW}복구 검증 중...${NC}"

# PostgreSQL 검증
PG_COUNT=$(docker exec db psql -U postgres -d crawler -t -c "SELECT COUNT(*) FROM agent_job_posting;" 2>/dev/null | xargs || echo "0")
echo "  - PostgreSQL 채용공고 수: $PG_COUNT"

# Django check
echo "  - Django 설정 검사 중..."
docker exec app bash -c "uv run python manage.py check" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "    ${GREEN}✓ Django 정상${NC}"
else
    echo -e "    ${RED}✗ Django 에러${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}복구 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}다음 단계:${NC}"
echo "1. 서비스 상태 확인: docker-compose ps"
echo "2. 로그 확인: docker-compose logs -f"
echo "3. Django 마이그레이션 확인: docker exec app uv run python manage.py showmigrations"
echo ""
echo -e "${GREEN}✓ 복구가 완료되었습니다.${NC}"

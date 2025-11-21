#!/bin/bash
# Job Crawler Backend - 롤백 스크립트
# Phase 실패 시 이전 체크포인트로 롤백

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 인자 확인
if [ $# -ne 1 ]; then
    echo -e "${RED}사용법: $0 <git_tag>${NC}"
    echo ""
    echo "사용 가능한 백업 태그:"
    git tag -l "backup-*" | tail -5 || echo "  (태그 없음)"
    exit 1
fi

TAG_NAME="$1"

# Git 태그 존재 확인
if ! git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
    echo -e "${RED}에러: Git 태그가 존재하지 않습니다: $TAG_NAME${NC}"
    exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}롤백 시작: $TAG_NAME${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 확인 메시지
echo -e "${RED}⚠️  경고: 현재 변경사항이 모두 삭제되고 $TAG_NAME 시점으로 돌아갑니다.${NC}"
read -p "계속하시겠습니까? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "롤백 취소됨"
    exit 0
fi

# 1. 현재 상태 저장 (롤백 실패 대비)
echo ""
echo -e "${YELLOW}[1/6] 현재 상태 저장 중...${NC}"
EMERGENCY_TAG="emergency-backup-$(date +%Y%m%d-%H%M%S)"
git tag -a "$EMERGENCY_TAG" -m "Emergency backup before rollback" 2>/dev/null || true
echo -e "${GREEN}✓ 긴급 백업 태그 생성: $EMERGENCY_TAG${NC}"

# 2. Git 체크아웃
echo -e "${YELLOW}[2/6] Git 체크아웃 중...${NC}"
git stash > /dev/null 2>&1 || true
git checkout "tags/$TAG_NAME" -b "rollback-$TAG_NAME" 2>/dev/null || git checkout "rollback-$TAG_NAME" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Git 체크아웃 완료${NC}"
else
    echo -e "${RED}✗ Git 체크아웃 실패${NC}"
    exit 1
fi

# 3. Docker 이미지 재빌드
echo -e "${YELLOW}[3/6] Docker 이미지 재빌드 중...${NC}"
docker-compose build --no-cache > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Docker 이미지 재빌드 완료${NC}"
else
    echo -e "${RED}✗ Docker 이미지 재빌드 실패${NC}"
    exit 1
fi

# 4. 컨테이너 재시작
echo -e "${YELLOW}[4/6] 컨테이너 재시작 중...${NC}"
docker-compose down > /dev/null 2>&1
docker-compose up -d > /dev/null 2>&1
sleep 10
echo -e "${GREEN}✓ 컨테이너 재시작 완료${NC}"

# 5. 데이터베이스 백업 찾기 및 복원 제안
echo -e "${YELLOW}[5/6] 데이터베이스 백업 확인 중...${NC}"
# 태그 날짜 추출 (backup-20251120-143000 형식)
TAG_DATE=$(echo "$TAG_NAME" | grep -oP '\d{8}' | head -1)
if [ -n "$TAG_DATE" ]; then
    MATCHING_BACKUP=$(find ./backups -type d -name "backup_${TAG_DATE}*" | head -1)
    if [ -n "$MATCHING_BACKUP" ]; then
        echo -e "${GREEN}✓ 일치하는 백업 발견: $MATCHING_BACKUP${NC}"
        echo ""
        read -p "이 백업으로 데이터베이스를 복원하시겠습니까? (yes/no): " RESTORE_DB
        if [ "$RESTORE_DB" = "yes" ]; then
            ./scripts/restore.sh "$MATCHING_BACKUP"
        fi
    else
        echo -e "${YELLOW}⚠ 일치하는 백업 없음 (수동 복원 필요할 수 있음)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ 백업 날짜 추출 실패${NC}"
fi

# 6. 마이그레이션 상태 확인
echo -e "${YELLOW}[6/6] 마이그레이션 상태 확인 중...${NC}"
docker exec app bash -c "uv run python manage.py showmigrations" > /tmp/migrations.txt 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 마이그레이션 상태 확인 완료${NC}"
    echo ""
    echo "현재 마이그레이션 상태:"
    cat /tmp/migrations.txt | grep -E "^\[|^ " | head -20
else
    echo -e "${RED}✗ 마이그레이션 상태 확인 실패${NC}"
fi

# 7. Celery worker 재시작
echo ""
echo -e "${YELLOW}Celery worker 재시작 중...${NC}"
docker-compose restart celery-worker > /dev/null 2>&1 || true
echo -e "${GREEN}✓ Celery worker 재시작 완료${NC}"

# 8. 서비스 정상 작동 확인
echo ""
echo -e "${YELLOW}서비스 정상 작동 확인 중...${NC}"
sleep 5
HEALTH_CHECK=$(curl -s http://localhost:8000/health/ 2>/dev/null | grep -o "healthy" || echo "")
if [ "$HEALTH_CHECK" = "healthy" ]; then
    echo -e "${GREEN}✓ 서비스 정상 작동 중${NC}"
else
    echo -e "${RED}✗ 서비스 응답 없음 (로그 확인 필요)${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}롤백 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}다음 단계:${NC}"
echo "1. 서비스 상태 확인: docker-compose ps"
echo "2. 로그 확인: docker-compose logs -f"
echo "3. API 테스트: curl http://localhost:8000/health/"
echo "4. 긴급 백업 확인: git tag | grep $EMERGENCY_TAG"
echo ""
echo -e "${GREEN}✓ $TAG_NAME 시점으로 롤백되었습니다.${NC}"
echo -e "${YELLOW}⚠ 문제가 계속되면 긴급 백업 태그를 사용하여 다시 롤백하세요.${NC}"

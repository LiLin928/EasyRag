#!/bin/bash

# EasyRAG 数据库初始化脚本
# 用于快速执行数据库初始化
# 使用方法: bash scripts/init-databases.sh

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
PG_HOST="192.168.137.13"
PG_USER="postgres"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INIT_SQL="$SCRIPT_DIR/../deploy/init-databases.sql"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}EasyRAG 数据库初始化${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查脚本文件
if [ ! -f "$INIT_SQL" ]; then
    echo -e "${RED}错误: 找不到初始化脚本 $INIT_SQL${NC}"
    exit 1
fi

echo -e "${YELLOW}步骤 1/4: 检查 PostgreSQL 连接...${NC}"
if ! psql -U $PG_USER -h $PG_HOST -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${RED}错误: 无法连接到 PostgreSQL ($PG_HOST)${NC}"
    echo -e "${YELLOW}提示: 请确保 PostgreSQL 正在运行且允许远程连接${NC}"
    exit 1
fi
echo -e "${GREEN}✓ PostgreSQL 连接成功${NC}"
echo ""

echo -e "${YELLOW}步骤 2/4: 执行数据库初始化脚本...${NC}"
if psql -U $PG_USER -h $PG_HOST -f "$INIT_SQL"; then
    echo -e "${GREEN}✓ 数据库初始化成功${NC}"
else
    echo -e "${RED}错误: 数据库初始化失败${NC}"
    exit 1
fi
echo ""

echo -e "${YELLOW}步骤 3/4: 验证数据库创建...${NC}
echo "数据库列表:"
psql -U $PG_USER -h $PG_HOST -c "\l" | grep -E "easyrag|langfuse"
echo ""

echo "用户列表:"
psql -U $PG_USER -h $PG_HOST -c "\du" | grep -E "easyrag|langfuse"
echo ""

echo -e "${YELLOW}步骤 4/4: 验证扩展...${NC}
echo "easyrag_v2 扩展:"
psql -U $PG_USER -h $PG_HOST -d easyrag_v2 -c "\dx"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}初始化完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "已创建:"
echo "  - 数据库: easyrag (V1), easyrag_v2 (V2), langfuse"
echo "  - 用户: easyrag, langfuse"
echo "  - 扩展: vector, pg_trgm, uuid-ossp"
echo ""
echo "下一步:"
echo "  1. 验证后端配置: cd backend && uv run python -c 'from app.config import settings; print(settings.database_url)'"
echo "  2. 运行测试: cd backend && uv run pytest tests/test_health.py -v"
echo ""
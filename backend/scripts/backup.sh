#!/bin/bash
# EasyRAG 统一备份脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"

echo "=== EasyRAG Backup ==="
echo "Backup directory: $BACKUP_DIR"
echo "Keep days: $KEEP_DAYS"
echo ""

# 1. 数据库备份
echo "[1/2] Backing up database..."
cd "$SCRIPT_DIR/.."
python scripts/backup_db.py

# 2. 存储备份（如果是 MinIO）
echo "[2/2] Backing up storage..."
if [ "${STORAGE_TYPE:-local}" = "minio" ]; then
    python scripts/backup_storage.py
else
    echo "Skipping storage backup (local storage)"
fi

# 3. 清理旧备份
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$KEEP_DAYS -delete 2>/dev/null || true
find "$BACKUP_DIR/storage" -type f -mtime +$KEEP_DAYS -delete 2>/dev/null || true

echo ""
echo "=== Backup completed ==="

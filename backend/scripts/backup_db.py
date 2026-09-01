#!/usr/bin/env python3
"""PostgreSQL 数据库备份脚本。"""
import asyncio
import gzip
import os
from datetime import datetime
from pathlib import Path

import asyncpg
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "./backups"))
KEEP_DAYS = int(os.getenv("KEEP_DAYS", 7))


async def backup_database():
    """执行数据库备份。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"easyrag_db_{timestamp}.sql.gz"
    
    logger.info("Starting database backup", file=str(backup_file))
    
    conn = await asyncpg.connect(settings.database_url)
    try:
        # 使用 COPY 导出数据
        tables = ["users", "workflows", "documents", "chunks"]
        
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            f.write(f"-- EasyRAG Database Backup\n")
            f.write(f"-- Generated: {datetime.now().isoformat()}\n\n")
            
            for table in tables:
                rows = await conn.fetch(f"SELECT * FROM {table}")
                if rows:
                    f.write(f"-- Table: {table}\n")
                    for row in rows:
                        f.write(f"{dict(row)}\n")
                    f.write("\n")
        
        logger.info("Backup completed", file=str(backup_file))
    finally:
        await conn.close()
    
    return backup_file


def cleanup_old_backups():
    """清理过期备份。"""
    import time
    cutoff = time.time() - (KEEP_DAYS * 24 * 3600)
    
    for backup_file in BACKUP_DIR.glob("*.sql.gz"):
        if backup_file.stat().st_mtime < cutoff:
            backup_file.unlink()
            logger.info("Deleted old backup", file=str(backup_file))


async def main():
    """入口函数。"""
    backup_file = await backup_database()
    cleanup_old_backups()
    print(f"Backup saved to: {backup_file}")


if __name__ == "__main__":
    asyncio.run(main())

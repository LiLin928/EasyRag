#!/usr/bin/env python3
"""MinIO 存储备份脚本。"""
import os
from datetime import datetime
from pathlib import Path

from minio import Minio

from app.config import settings

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "./backups/storage"))


def backup_minio():
    """备份 MinIO bucket 到本地。"""
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    objects = client.list_objects(settings.minio_bucket, recursive=True)
    
    count = 0
    for obj in objects:
        local_path = BACKUP_DIR / obj.object_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        client.fget_object(settings.minio_bucket, obj.object_name, str(local_path))
        count += 1
        print(f"Backed up: {obj.object_name}")
    
    print(f"Storage backup completed: {count} files to {BACKUP_DIR}")


if __name__ == "__main__":
    backup_minio()

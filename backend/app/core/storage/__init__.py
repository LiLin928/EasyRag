"""存储模块入口。"""
from app.config import settings
from app.core.storage.local import LocalStorage
from app.core.storage.minio import MinioStorage

_storage = None


def get_storage():
    """获取存储实例（单例工厂）。
    
    根据配置返回本地存储或 MinIO 存储实例。
    
    Returns:
        StorageInterface 实现实例
    """
    global _storage
    if _storage is None:
        if settings.storage_type == "minio":
            _storage = MinioStorage()
        else:
            _storage = LocalStorage(settings.storage_local_dir)
    return _storage


__all__ = ["get_storage", "LocalStorage", "MinioStorage"]

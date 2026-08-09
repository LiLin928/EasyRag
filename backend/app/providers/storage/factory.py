"""对象存储工厂，按 settings.storage_type 选择实现。"""
from app.config import settings
from app.providers.storage.base import ObjectStorage


def get_storage() -> ObjectStorage:
    """返回配置的对象存储实例（local | minio）。"""
    if settings.storage_type == "minio":
        from app.providers.storage.minio_impl import MinioStorage  # Phase3 实现
        return MinioStorage()
    from app.providers.storage.local_fs import LocalFSStorage
    return LocalFSStorage(settings.storage_local_dir)

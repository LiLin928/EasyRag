"""对象存储工厂，按 settings.storage_type 选择实现。"""
from app.config import settings
from app.providers.storage.base import ObjectStorage


def get_storage() -> ObjectStorage:
    """返回配置的对象存储实例（local | minio）。"""
    if settings.storage_type == "minio":
        # MinIO 实现将在 Phase3 添加
        # from app.providers.storage.minio_impl import MinioStorage
        # return MinioStorage()
        # 目前暂时使用本地文件系统
        from app.providers.storage.local_fs import LocalFSStorage
        return LocalFSStorage(settings.storage_local_dir)
    from app.providers.storage.local_fs import LocalFSStorage
    return LocalFSStorage(settings.storage_local_dir)

"""对象存储工厂，按 settings.storage_type 选择实现。"""
from app.core.storage import get_storage as core_get_storage


def get_storage():
    """返回配置的对象存储实例（local | minio）。

    统一调用 app.core.storage 工厂，支持本地文件系统和 MinIO。
    """
    return core_get_storage()
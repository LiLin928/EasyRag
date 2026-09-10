"""存储健康检查。"""
from app.core.storage import get_storage
from app.config import settings


async def check_storage_health() -> dict:
    """检查存储系统健康状态。

    Returns:
        健康状态字典，包含：
        - status: healthy / unhealthy
        - storage_type: local / minio
        - details: 详细信息
    """
    try:
        storage = get_storage()

        if settings.storage_type == "minio":
            # 测试 MinIO 连接：尝试列出一个不存在的对象
            await storage.list_objects(prefix="__health_check__")

            return {
                "status": "healthy",
                "storage_type": "minio",
                "details": {
                    "endpoint": settings.minio_endpoint,
                    "bucket": settings.minio_bucket,
                }
            }
        else:
            return {
                "status": "healthy",
                "storage_type": "local",
                "details": {
                    "base_dir": settings.storage_local_dir,
                }
            }

    except Exception as e:
        return {
            "status": "unhealthy",
            "storage_type": settings.storage_type,
            "error": str(e)
        }
"""对象存储抽象基类。"""
from abc import ABC, abstractmethod


class ObjectStorage(ABC):
    """对象存储统一抽象（本地 FS / MinIO）。"""

    @abstractmethod
    async def put(self, key: str, data: bytes) -> None:
        """写入对象。"""

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """读取对象字节。"""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """删除对象。"""

    @abstractmethod
    async def presigned_url(self, key: str, expires: int = 3600) -> str:
        """返回可访问的 URL（本地 FS 为静态路由，MinIO 为预签名 URL）。"""

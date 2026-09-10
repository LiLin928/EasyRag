"""存储服务代理层。

提供统一的存储服务接口，封装底层的存储实现细节。
"""
from typing import Optional, List
from app.core.storage import get_storage
from app.core.storage.interface import StorageInterface


class StorageService:
    """存储服务代理层。

    封装存储操作，提供业务友好的接口。
    """

    def __init__(self):
        """初始化存储服务。"""
        self._storage: StorageInterface = get_storage()

    async def upload_file(
        self,
        file_id: str,
        content: bytes,
        extension: str = "",
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """上传文件。

        Args:
            file_id: 文件唯一标识
            content: 文件字节内容
            extension: 文件扩展名（可选）
            content_type: 内容类型（可选）
            metadata: 元数据（可选）

        Returns:
            文件访问 URL
        """
        key = f"{file_id}"
        if extension:
            key = f"{file_id}.{extension.lstrip('.')}"

        return await self._storage.upload(key, content, content_type, metadata)

    async def download_file(self, file_id: str, extension: str = "") -> bytes:
        """下载文件。

        Args:
            file_id: 文件唯一标识
            extension: 文件扩展名（可选）

        Returns:
            文件字节内容
        """
        key = f"{file_id}"
        if extension:
            key = f"{file_id}.{extension.lstrip('.')}"

        return await self._storage.download(key)

    async def delete_file(self, file_id: str, extension: str = "") -> None:
        """删除文件。

        Args:
            file_id: 文件唯一标识
            extension: 文件扩展名（可选）
        """
        key = f"{file_id}"
        if extension:
            key = f"{file_id}.{extension.lstrip('.')}"

        await self._storage.delete(key)

    async def file_exists(self, file_id: str, extension: str = "") -> bool:
        """检查文件是否存在。

        Args:
            file_id: 文件唯一标识
            extension: 文件扩展名（可选）

        Returns:
            文件是否存在
        """
        key = f"{file_id}"
        if extension:
            key = f"{file_id}.{extension.lstrip('.')}"

        return await self._storage.exists(key)

    async def get_file_metadata(self, file_id: str, extension: str = "") -> Optional[dict]:
        """获取文件元数据。

        Args:
            file_id: 文件唯一标识
            extension: 文件扩展名（可选）

        Returns:
            元数据字典，包含：
            - size: 文件大小（字节）
            - content_type: 内容类型
            - last_modified: 最后修改时间
            - etag: ETag
            - metadata: 自定义元数据
        """
        key = f"{file_id}"
        if extension:
            key = f"{file_id}.{extension.lstrip('.')}"

        return await self._storage.get_metadata(key)

    async def list_files(
        self,
        prefix: str = "",
        recursive: bool = True,
    ) -> List[str]:
        """列出文件。

        Args:
            prefix: 前缀过滤
            recursive: 是否递归

        Returns:
            文件键列表
        """
        return await self._storage.list_objects(prefix, recursive)

    async def copy_file(
        self,
        source_file_id: str,
        dest_file_id: str,
        extension: str = "",
    ) -> str:
        """复制文件。

        Args:
            source_file_id: 源文件唯一标识
            dest_file_id: 目标文件唯一标识
            extension: 文件扩展名（可选）

        Returns:
            新文件访问 URL
        """
        source_key = f"{source_file_id}"
        dest_key = f"{dest_file_id}"
        if extension:
            source_key = f"{source_file_id}.{extension.lstrip('.')}"
            dest_key = f"{dest_file_id}.{extension.lstrip('.')}"

        return await self._storage.copy(source_key, dest_key)

    async def get_presigned_url(
        self,
        file_id: str,
        extension: str = "",
        expires: int = 3600,
    ) -> str:
        """获取预签名 URL（用于临时访问）。

        Args:
            file_id: 文件唯一标识
            extension: 文件扩展名（可选）
            expires: 过期时间（秒）

        Returns:
            预签名 URL

        Raises:
            NotImplementedError: 本地存储不支持预签名 URL
        """
        key = f"{file_id}"
        if extension:
            key = f"{file_id}.{extension.lstrip('.')}"

        return await self._storage.get_presigned_url(key, expires)

    async def get_file_size(self, file_id: str, extension: str = "") -> int:
        """获取文件大小。

        Args:
            file_id: 文件唯一标识
            extension: 文件扩展名（可选）

        Returns:
            文件大小（字节）
        """
        key = f"{file_id}"
        if extension:
            key = f"{file_id}.{extension.lstrip('.')}"

        return await self._storage.get_size(key)


# 全局单例
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """获取存储服务单例。
    
    Returns:
        StorageService 实例
    """
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service

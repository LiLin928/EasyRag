"""存储接口定义。"""
from typing import Protocol, runtime_checkable, Optional, List
from datetime import datetime


@runtime_checkable
class StorageInterface(Protocol):
    """存储抽象接口。

    定义了存储后端必须实现的方法，支持本地文件系统和 MinIO 对象存储。
    """

    async def upload(
        self,
        key: str,
        content: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """上传文件内容。

        Args:
            key: 对象键
            content: 文件内容
            content_type: 内容类型（可选）
            metadata: 元数据（可选）

        Returns:
            对象 URL 或路径
        """
        ...

    async def download(self, key: str) -> bytes:
        """下载文件内容。

        Args:
            key: 对象键

        Returns:
            文件内容

        Raises:
            FileNotFoundError: 文件不存在
        """
        ...

    async def delete(self, key: str) -> None:
        """删除文件。

        Args:
            key: 对象键
        """
        ...

    async def exists(self, key: str) -> bool:
        """检查文件是否存在。

        Args:
            key: 对象键

        Returns:
            是否存在
        """
        ...

    async def get_metadata(self, key: str) -> Optional[dict]:
        """获取对象元数据。

        Args:
            key: 对象键

        Returns:
            元数据字典，包含：
            - size: 文件大小（字节）
            - content_type: 内容类型
            - last_modified: 最后修改时间
            - etag: ETag
            - metadata: 自定义元数据

        Raises:
            FileNotFoundError: 文件不存在
        """
        ...

    async def list_objects(
        self,
        prefix: str = "",
        recursive: bool = True,
    ) -> List[str]:
        """列出对象。

        Args:
            prefix: 前缀过滤
            recursive: 是否递归

        Returns:
            对象键列表
        """
        ...

    async def copy(
        self,
        source_key: str,
        dest_key: str,
    ) -> str:
        """复制对象。

        Args:
            source_key: 源对象键
            dest_key: 目标对象键

        Returns:
            新对象 URL

        Raises:
            FileNotFoundError: 源对象不存在
        """
        ...

    async def get_presigned_url(
        self,
        key: str,
        expires: int = 3600,
    ) -> str:
        """获取预签名 URL（用于临时访问）。

        Args:
            key: 对象键
            expires: 过期时间（秒）

        Returns:
            预签名 URL

        Note:
            本地存储实现应返回 404 或抛出 NotImplementedError
        """
        ...

    async def get_size(self, key: str) -> int:
        """获取对象大小。

        Args:
            key: 对象键

        Returns:
            文件大小（字节）

        Raises:
            FileNotFoundError: 文件不存在
        """
        ...

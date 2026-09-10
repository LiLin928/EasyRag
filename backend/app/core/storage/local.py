"""本地文件系统存储实现。"""
import os
import shutil
from pathlib import Path
from typing import Optional, List
import logging

from app.exceptions import BizException, ErrorCode


logger = logging.getLogger(__name__)


class LocalStorage:
    """本地文件系统存储实现。"""

    def __init__(self, base_dir: str):
        """初始化本地存储。

        Args:
            base_dir: 基础目录路径
        """
        self.base_path = Path(base_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, key: str) -> Path:
        """获取文件完整路径。

        Args:
            key: 对象键

        Returns:
            文件完整路径

        Raises:
            BizException: 非法文件路径
        """
        key = key.lstrip("/")
        path = self.base_path / key
        try:
            path.relative_to(self.base_path)
        except ValueError:
            raise BizException(ErrorCode.PARAM_ERROR, "非法文件路径")
        return path

    async def upload(
        self,
        key: str,
        content: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """上传文件到本地存储。

        Args:
            key: 对象键
            content: 文件内容
            content_type: 内容类型（可选，本地存储忽略）
            metadata: 元数据（可选，本地存储忽略）

        Returns:
            文件路径
        """
        file_path = self._get_path(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"Uploaded to local storage: {key} ({len(content)} bytes)")
        return str(file_path)
    
    async def download(self, key: str) -> bytes:
        """从本地存储下载文件。

        Args:
            key: 对象键

        Returns:
            文件内容

        Raises:
            FileNotFoundError: 文件不存在
        """
        file_path = self._get_path(key)

        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {key}")

        with open(file_path, "rb") as f:
            data = f.read()

        logger.info(f"Downloaded from local storage: {key} ({len(data)} bytes)")
        return data

    async def delete(self, key: str) -> None:
        """从本地存储删除文件。

        Args:
            key: 对象键
        """
        file_path = self._get_path(key)

        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted from local storage: {key}")

    async def exists(self, key: str) -> bool:
        """检查本地文件是否存在。

        Args:
            key: 对象键

        Returns:
            是否存在
        """
        file_path = self._get_path(key)
        return file_path.exists() and file_path.is_file()

    async def get_metadata(self, key: str) -> Optional[dict]:
        """获取文件元数据。

        Args:
            key: 对象键

        Returns:
            元数据字典，包含：
            - size: 文件大小（字节）
            - content_type: 内容类型
            - last_modified: 最后修改时间
            - etag: ETag（本地存储为 None）
            - metadata: 自定义元数据（本地存储为空字典）

        Raises:
            FileNotFoundError: 文件不存在
        """
        file_path = self._get_path(key)

        if not file_path.exists():
            return None

        stat = file_path.stat()

        return {
            "size": stat.st_size,
            "content_type": "application/octet-stream",
            "last_modified": stat.st_mtime,
            "etag": None,
            "metadata": {},
        }

    async def list_objects(
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
        prefix = prefix.lstrip("/")
        search_path = self.base_path / prefix

        if not search_path.exists():
            return []

        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        objects = [
            str(p.relative_to(self.base_path)).replace("\\", "/")
            for p in search_path.glob(pattern)
            if p.is_file()
        ]

        logger.info(f"Listed {len(objects)} objects with prefix '{prefix}'")
        return objects

    async def copy(
        self,
        source_key: str,
        dest_key: str,
    ) -> str:
        """复制文件。

        Args:
            source_key: 源对象键
            dest_key: 目标对象键

        Returns:
            新文件路径

        Raises:
            FileNotFoundError: 源文件不存在
        """
        source_path = self._get_path(source_key)
        dest_path = self._get_path(dest_key)

        if not source_path.exists():
            raise FileNotFoundError(f"源文件不存在: {source_key}")

        # 创建目标目录
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # 复制文件
        shutil.copy2(source_path, dest_path)

        logger.info(f"Copied {source_key} to {dest_key}")
        return str(dest_path)

    async def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        """本地存储不支持预签名 URL。

        Args:
            key: 对象键
            expires: 过期时间（秒，忽略）

        Returns:
            无

        Raises:
            NotImplementedError: 本地存储不支持预签名 URL
        """
        raise NotImplementedError("本地存储不支持预签名 URL")

    async def get_size(self, key: str) -> int:
        """获取文件大小。

        Args:
            key: 对象键

        Returns:
            文件大小（字节）

        Raises:
            FileNotFoundError: 文件不存在
        """
        metadata = await self.get_metadata(key)
        if metadata is None:
            raise FileNotFoundError(f"文件不存在: {key}")
        return metadata["size"]

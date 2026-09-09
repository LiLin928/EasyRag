"""本地文件系统对象存储实现。"""
import os
import urllib.parse

import aiofiles

from app.providers.storage.base import ObjectStorage


class LocalFSStorage(ObjectStorage):
    """本地 FS 存储，按 key 映射到 root/<key> 路径。

    Attributes:
        root: 存储根目录。
    """

    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self.root, key)

    async def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)

    async def get(self, key: str) -> bytes:
        async with aiofiles.open(self._path(key), "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)

    async def presigned_url(self, key: str, expires: int = 3600) -> str:
        # 本地 FS：返回 /files/<key> 静态路由（Nginx 或 FastAPI StaticFiles 提供）
        return "/files/" + urllib.parse.quote(key)

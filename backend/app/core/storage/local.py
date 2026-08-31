"""本地文件系统存储实现。"""
import os
from pathlib import Path

from app.exceptions import BizException, ErrorCode


class LocalStorage:
    """本地文件系统存储实现。"""
    
    def __init__(self, base_dir: str):
        """初始化本地存储。"""
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, key: str) -> Path:
        """获取文件完整路径。"""
        key = key.lstrip("/")
        path = self.base_dir / key
        try:
            path.relative_to(self.base_dir)
        except ValueError:
            raise BizException(ErrorCode.PARAM_ERROR, "非法文件路径")
        return path
    
    async def upload(self, key: str, content: bytes) -> str:
        """上传文件到本地存储。"""
        file_path = self._get_path(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        return str(file_path)
    
    async def download(self, key: str) -> bytes:
        """从本地存储下载文件。"""
        file_path = self._get_path(key)
        
        if not file_path.exists():
            raise BizException(ErrorCode.NOT_FOUND, f"文件不存在: {key}")
        
        with open(file_path, "rb") as f:
            return f.read()
    
    async def delete(self, key: str) -> None:
        """从本地存储删除文件。"""
        file_path = self._get_path(key)
        
        if file_path.exists():
            file_path.unlink()
    
    async def exists(self, key: str) -> bool:
        """检查本地文件是否存在。"""
        file_path = self._get_path(key)
        return file_path.exists() and file_path.is_file()

"""存储接口定义。"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageInterface(Protocol):
    """存储抽象接口。
    
    定义了存储后端必须实现的方法，支持本地文件系统和 MinIO 对象存储。
    """
    
    async def upload(self, key: str, content: bytes) -> str:
        """上传文件内容。"""
        ...
    
    async def download(self, key: str) -> bytes:
        """下载文件内容。"""
        ...
    
    async def delete(self, key: str) -> None:
        """删除文件。"""
        ...
    
    async def exists(self, key: str) -> bool:
        """检查文件是否存在。"""
        ...

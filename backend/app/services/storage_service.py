"""存储服务代理层。

提供统一的存储服务接口，封装底层的存储实现细节。
"""
from app.core.storage import get_storage
from app.core.storage.interface import StorageInterface


class StorageService:
    """存储服务代理层。
    
    封装存储操作，提供业务友好的接口。
    """
    
    def __init__(self):
        """初始化存储服务。"""
        self._storage: StorageInterface = get_storage()
    
    async def upload_file(self, file_id: str, content: bytes, extension: str = "") -> str:
        """上传文件。
        
        Args:
            file_id: 文件唯一标识
            content: 文件字节内容
            extension: 文件扩展名（可选）
            
        Returns:
            文件访问 URL
        """
        key = f"{file_id}"
        if extension:
            key = f"{file_id}.{extension.lstrip(".")}"
        
        return await self._storage.upload(key, content)
    
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
            key = f"{file_id}.{extension.lstrip(".")}"
        
        return await self._storage.download(key)
    
    async def delete_file(self, file_id: str, extension: str = "") -> None:
        """删除文件。
        
        Args:
            file_id: 文件唯一标识
            extension: 文件扩展名（可选）
        """
        key = f"{file_id}"
        if extension:
            key = f"{file_id}.{extension.lstrip(".")}"
        
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
            key = f"{file_id}.{extension.lstrip(".")}"
        
        return await self._storage.exists(key)


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

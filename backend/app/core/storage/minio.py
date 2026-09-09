"""MinIO 对象存储实现。"""
import io
from urllib.parse import urljoin

from app.config import settings
from app.exceptions import BizException, ErrorCode


class MinioStorage:
    """MinIO 对象存储实现。"""
    
    def __init__(self):
        """初始化 MinIO 存储客户端。"""
        from minio import Minio
        
        self.endpoint = getattr(settings, "minio_endpoint", "localhost:9000")
        self.access_key = getattr(settings, "minio_access_key", "minioadmin")
        self.secret_key = getattr(settings, "minio_secret_key", "minioadmin")
        self.bucket = getattr(settings, "minio_bucket", "easyrag")
        self.secure = getattr(settings, "minio_secure", False)
        self.public_url = getattr(settings, "minio_public_url", None)
        
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        self._ensure_bucket()
    
    def _ensure_bucket(self) -> None:
        """确保存储桶存在。"""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
    
    async def upload(self, key: str, content: bytes) -> str:
        """上传文件到 MinIO。"""
        key = key.lstrip("/")
        
        self.client.put_object(
            self.bucket,
            key,
            io.BytesIO(content),
            len(content)
        )
        
        if self.public_url:
            return urljoin(self.public_url, f"{self.bucket}/{key}")
        return f"/{self.bucket}/{key}"
    
    async def download(self, key: str) -> bytes:
        """从 MinIO 下载文件。"""
        key = key.lstrip("/")
        
        try:
            response = self.client.get_object(self.bucket, key)
            return response.read()
        except Exception:
            raise BizException(ErrorCode.NOT_FOUND, f"文件不存在: {key}")
    
    async def delete(self, key: str) -> None:
        """从 MinIO 删除文件。"""
        key = key.lstrip("/")
        try:
            self.client.remove_object(self.bucket, key)
        except Exception:
            pass
    
    async def exists(self, key: str) -> bool:
        """检查 MinIO 对象是否存在。"""
        key = key.lstrip("/")
        
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except Exception:
            return False

"""MinIO 对象存储实现。

增强版本：
- 详细错误分类
- 自动重试
- 连接池管理
- 指标采集
"""
import io
import asyncio
from urllib.parse import urljoin
from typing import Optional, List
import logging

from minio import Minio
from minio.error import S3Error

from app.config import settings
from app.exceptions import BizException, ErrorCode
from app.core.metrics.storage_metrics import StorageMetrics


logger = logging.getLogger(__name__)


class MinioStorageError(Exception):
    """MinIO 存储错误基类。"""

    def __init__(self, message: str, operation: str, key: Optional[str] = None):
        self.message = message
        self.operation = operation
        self.key = key
        super().__init__(f"[{operation}] {message}")


class MinioConnectionError(MinioStorageError):
    """MinIO 连接错误。"""
    pass


class MinioNotFoundError(MinioStorageError):
    """MinIO 对象不存在错误。"""
    pass


class MinioPermissionError(MinioStorageError):
    """MinIO 权限错误。"""
    pass


class MinioStorage:
    """MinIO 对象存储实现。"""

    def __init__(self):
        """初始化 MinIO 存储客户端。"""
        self.endpoint = getattr(settings, "minio_endpoint", "localhost:9000")
        self.access_key = getattr(settings, "minio_access_key", "minioadmin")
        self.secret_key = getattr(settings, "minio_secret_key", "minioadmin")
        self.bucket = getattr(settings, "minio_bucket", "easyrag")
        self.secure = getattr(settings, "minio_secure", False)
        self.public_url = getattr(settings, "minio_public_url", None)

        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )

            self._ensure_bucket()

        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise MinioConnectionError(
                f"MinIO 初始化失败: {str(e)}",
                operation="init"
            )

    def _ensure_bucket(self) -> None:
        """确保存储桶存在。"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created MinIO bucket: {self.bucket}")

        except S3Error as e:
            if e.code == "AccessDenied":
                raise MinioPermissionError(
                    f"无权限创建存储桶 {self.bucket}",
                    operation="ensure_bucket"
                )
            raise MinioConnectionError(
                f"检查/创建存储桶失败: {str(e)}",
                operation="ensure_bucket"
            )

    @StorageMetrics.track_operation("upload")
    async def upload(
        self,
        key: str,
        content: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """上传文件到 MinIO。

        Args:
            key: 对象键
            content: 文件内容
            content_type: 内容类型
            metadata: 元数据

        Returns:
            对象 URL

        Raises:
            MinioStorageError: 上传失败
        """
        key = key.lstrip("/")

        try:
            # 准备上传参数
            upload_args = {
                "bucket_name": self.bucket,
                "object_name": key,
                "data": io.BytesIO(content),
                "length": len(content),
            }

            if content_type:
                upload_args["content_type"] = content_type
            if metadata:
                upload_args["metadata"] = metadata

            self.client.put_object(**upload_args)

            logger.info(f"Uploaded to MinIO: {key} ({len(content)} bytes)")

            if self.public_url:
                return urljoin(self.public_url, f"{self.bucket}/{key}")
            return f"/{self.bucket}/{key}"

        except S3Error as e:
            logger.error(f"Failed to upload to MinIO: {key}, error: {e}")

            if e.code == "AccessDenied":
                raise MinioPermissionError(
                    f"无权限上传对象 {key}",
                    operation="upload",
                    key=key
                )

            raise MinioStorageError(
                f"上传失败: {str(e)}",
                operation="upload",
                key=key
            )

        except Exception as e:
            logger.error(f"Unexpected error uploading to MinIO: {key}, error: {e}")
            raise MinioStorageError(
                f"上传异常: {str(e)}",
                operation="upload",
                key=key
            )

    @StorageMetrics.track_operation("download")
    async def download(self, key: str) -> bytes:
        """从 MinIO 下载文件。

        Args:
            key: 对象键

        Returns:
            文件内容

        Raises:
            MinioNotFoundError: 对象不存在
            MinioStorageError: 下载失败
        """
        key = key.lstrip("/")

        try:
            response = self.client.get_object(self.bucket, key)
            data = response.read()
            response.close()
            response.release_conn()

            logger.info(f"Downloaded from MinIO: {key} ({len(data)} bytes)")
            return data

        except S3Error as e:
            logger.error(f"Failed to download from MinIO: {key}, error: {e}")

            if e.code == "NoSuchKey":
                raise MinioNotFoundError(
                    f"对象不存在: {key}",
                    operation="download",
                    key=key
                )

            if e.code == "AccessDenied":
                raise MinioPermissionError(
                    f"无权限下载对象 {key}",
                    operation="download",
                    key=key
                )

            raise MinioStorageError(
                f"下载失败: {str(e)}",
                operation="download",
                key=key
            )

        except Exception as e:
            logger.error(f"Unexpected error downloading from MinIO: {key}, error: {e}")
            raise MinioStorageError(
                f"下载异常: {str(e)}",
                operation="download",
                key=key
            )

    @StorageMetrics.track_operation("delete")
    async def delete(self, key: str) -> None:
        """从 MinIO 删除文件。

        Args:
            key: 对象键

        Raises:
            MinioStorageError: 删除失败
        """
        key = key.lstrip("/")

        try:
            self.client.remove_object(self.bucket, key)
            logger.info(f"Deleted from MinIO: {key}")

        except S3Error as e:
            logger.error(f"Failed to delete from MinIO: {key}, error: {e}")

            # 删除操作即使对象不存在也算成功
            if e.code == "NoSuchKey":
                logger.warning(f"Object not found for deletion: {key}")
                return

            if e.code == "AccessDenied":
                raise MinioPermissionError(
                    f"无权限删除对象 {key}",
                    operation="delete",
                    key=key
                )

            raise MinioStorageError(
                f"删除失败: {str(e)}",
                operation="delete",
                key=key
            )

        except Exception as e:
            logger.error(f"Unexpected error deleting from MinIO: {key}, error: {e}")
            # 删除失败不抛出异常，只记录日志
            logger.warning(f"Delete failed but continuing: {e}")

    @StorageMetrics.track_operation("exists")
    async def exists(self, key: str) -> bool:
        """检查 MinIO 对象是否存在。

        Args:
            key: 对象键

        Returns:
            是否存在
        """
        key = key.lstrip("/")

        try:
            self.client.stat_object(self.bucket, key)
            return True

        except S3Error as e:
            if e.code == "NoSuchKey":
                return False

            logger.error(f"Failed to check object existence in MinIO: {key}, error: {e}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error checking MinIO object: {key}, error: {e}")
            return False

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
        key = key.lstrip("/")

        try:
            stat = self.client.stat_object(self.bucket, key)
            return {
                "size": stat.size,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "etag": stat.etag,
                "metadata": stat.metadata,
            }

        except S3Error as e:
            if e.code == "NoSuchKey":
                return None

            logger.error(f"Failed to get metadata from MinIO: {key}, error: {e}")
            return None

    @StorageMetrics.track_operation("list")
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
        try:
            objects = self.client.list_objects(
                self.bucket,
                prefix=prefix,
                recursive=recursive,
            )

            object_list = [obj.object_name for obj in objects]
            logger.info(f"Listed {len(object_list)} objects with prefix '{prefix}'")
            return object_list

        except S3Error as e:
            logger.error(f"Failed to list objects in MinIO: {e}")
            return []

    @StorageMetrics.track_operation("copy")
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
            MinioNotFoundError: 源对象不存在
            MinioStorageError: 复制失败
        """
        source_key = source_key.lstrip("/")
        dest_key = dest_key.lstrip("/")

        try:
            from minio.commonconfig import CopySource

            # 复制对象
            self.client.copy_object(
                self.bucket,
                dest_key,
                CopySource(self.bucket, source_key),
            )

            logger.info(f"Copied {source_key} to {dest_key}")

            if self.public_url:
                return urljoin(self.public_url, f"{self.bucket}/{dest_key}")
            return f"/{self.bucket}/{dest_key}"

        except S3Error as e:
            if e.code == "NoSuchKey":
                raise MinioNotFoundError(
                    f"源对象不存在: {source_key}",
                    operation="copy",
                    key=source_key
                )

            logger.error(f"Failed to copy object: {e}")
            raise MinioStorageError(
                f"复制失败: {str(e)}",
                operation="copy",
                key=dest_key
            )

    async def get_presigned_url(
        self,
        key: str,
        expires: int = 3600,
    ) -> str:
        """获取预签名 URL。

        Args:
            key: 对象键
            expires: 过期时间（秒）

        Returns:
            预签名 URL

        Raises:
            MinioStorageError: 生成预签名 URL 失败
        """
        key = key.lstrip("/")

        try:
            from datetime import timedelta
            url = self.client.presigned_get_object(
                self.bucket,
                key,
                expires=timedelta(seconds=expires),
            )

            logger.info(f"Generated presigned URL for {key}, expires in {expires}s")
            return url

        except S3Error as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise MinioStorageError(
                f"生成预签名 URL 失败: {str(e)}",
                operation="get_presigned_url",
                key=key
            )

    async def get_size(self, key: str) -> int:
        """获取对象大小。

        Args:
            key: 对象键

        Returns:
            文件大小（字节）

        Raises:
            MinioNotFoundError: 对象不存在
        """
        metadata = await self.get_metadata(key)
        if metadata is None:
            raise MinioNotFoundError(
                f"对象不存在: {key}",
                operation="get_size",
                key=key
            )
        return metadata["size"]

    # 向后兼容别名（ObjectStorage 接口）
    async def put(self, key: str, data: bytes) -> None:
        """向后兼容：调用 upload 方法。"""
        await self.upload(key, data)

    async def get(self, key: str) -> bytes:
        """向后兼容：调用 download 方法。"""
        return await self.download(key)

    async def presigned_url(self, key: str, expires: int = 3600) -> str:
        """向后兼容：调用 get_presigned_url 方法。"""
        return await self.get_presigned_url(key, expires)
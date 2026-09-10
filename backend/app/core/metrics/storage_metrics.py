"""存储层指标采集。"""
from prometheus_client import Counter, Histogram, Gauge
from functools import wraps
import time

from app.config import settings

# 指标定义
STORAGE_OPERATIONS_TOTAL = Counter(
    f"{settings.metrics_namespace}_storage_operations_total",
    "Total storage operations",
    ["operation", "status"]
)

STORAGE_OPERATION_DURATION = Histogram(
    f"{settings.metrics_namespace}_storage_operation_duration_seconds",
    "Storage operation duration in seconds",
    ["operation"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
)

STORAGE_BYTES_TRANSFERRED = Counter(
    f"{settings.metrics_namespace}_storage_bytes_transferred_total",
    "Total bytes transferred",
    ["operation", "direction"]
)

STORAGE_ACTIVE_OPERATIONS = Gauge(
    f"{settings.metrics_namespace}_storage_active_operations",
    "Number of active storage operations",
    ["operation"]
)


class StorageMetrics:
    """存储指标采集装饰器。

    提供装饰器模式跟踪存储层操作，包括：
    - 操作计数（成功/失败）
    - 操作延迟分布
    - 传输字节数
    - 活跃操作数
    """

    @staticmethod
    def track_operation(operation: str):
        """跟踪存储操作。

        Args:
            operation: 操作类型（upload, download, delete, exists, copy, list）

        Returns:
            装饰器函数，用于包装存储操作方法

        示例:
            @StorageMetrics.track_operation("upload")
            async def upload(self, path: str, content: bytes) -> str:
                ...
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 增加活跃操作数
                STORAGE_ACTIVE_OPERATIONS.labels(operation=operation).inc()

                # 记录开始时间
                start_time = time.time()
                status = "success"

                try:
                    result = await func(*args, **kwargs)

                    # 记录传输字节数（仅 upload/download）
                    if operation in ["upload", "download"]:
                        if operation == "upload":
                            # 获取上传内容大小
                            # args[0] 是 self，args[1] 可能是 path 或 content
                            # kwargs 中查找 content
                            bytes_count = len(kwargs.get("content", args[1] if len(args) > 1 else b""))
                            STORAGE_BYTES_TRANSFERRED.labels(
                                operation=operation,
                                direction="in"
                            ).inc(bytes_count)
                        elif operation == "download":
                            # download 操作返回 bytes
                            STORAGE_BYTES_TRANSFERRED.labels(
                                operation=operation,
                                direction="out"
                            ).inc(len(result))

                    return result

                except Exception as e:
                    status = "error"
                    raise

                finally:
                    # 记录操作次数
                    STORAGE_OPERATIONS_TOTAL.labels(
                        operation=operation,
                        status=status
                    ).inc()

                    # 记录操作延迟
                    duration = time.time() - start_time
                    STORAGE_OPERATION_DURATION.labels(
                        operation=operation
                    ).observe(duration)

                    # 减少活跃操作数
                    STORAGE_ACTIVE_OPERATIONS.labels(operation=operation).dec()

            return wrapper
        return decorator
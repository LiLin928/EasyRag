"""SSE 连接管理器。

追踪活跃的 SSE 连接，自动清理过期连接。
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Set
import logging


logger = logging.getLogger(__name__)


@dataclass
class SSEConnection:
    """SSE 连接信息。"""
    connection_id: str
    stream_key: str
    created_at: float
    last_activity: float
    client_ip: str = ""


class SSEConnectionManager:
    """SSE 连接管理器。"""

    def __init__(self, timeout_seconds: int = 300):
        """初始化连接管理器。

        Args:
            timeout_seconds: 连接超时时间（秒）
        """
        self.timeout = timeout_seconds
        self._connections: Dict[str, SSEConnection] = {}
        self._by_stream: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        connection_id: str,
        stream_key: str,
        client_ip: str = "",
    ) -> None:
        """注册新连接。

        Args:
            connection_id: 连接 ID
            stream_key: 订阅的流键
            client_ip: 客户端 IP
        """
        async with self._lock:
            now = time.time()
            conn = SSEConnection(
                connection_id=connection_id,
                stream_key=stream_key,
                created_at=now,
                last_activity=now,
                client_ip=client_ip,
            )

            self._connections[connection_id] = conn

            if stream_key not in self._by_stream:
                self._by_stream[stream_key] = set()
            self._by_stream[stream_key].add(connection_id)

            logger.info(
                f"SSE connection registered: {connection_id} "
                f"for stream {stream_key}, total={len(self._connections)}"
            )

    async def unregister(self, connection_id: str) -> None:
        """注销连接。

        Args:
            connection_id: 连接 ID
        """
        async with self._lock:
            conn = self._connections.pop(connection_id, None)
            if conn:
                # 从 stream 索引中移除
                if conn.stream_key in self._by_stream:
                    self._by_stream[conn.stream_key].discard(connection_id)
                    if not self._by_stream[conn.stream_key]:
                        del self._by_stream[conn.stream_key]

                logger.info(
                    f"SSE connection unregistered: {connection_id}, "
                    f"duration={time.time() - conn.created_at:.1f}s, "
                    f"remaining={len(self._connections)}"
                )

    async def update_activity(self, connection_id: str) -> None:
        """更新连接活动时间。

        Args:
            connection_id: 连接 ID
        """
        async with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].last_activity = time.time()

    async def cleanup_expired(self) -> int:
        """清理过期连接。

        Returns:
            清理的连接数量
        """
        async with self._lock:
            now = time.time()
            expired = [
                conn_id
                for conn_id, conn in self._connections.items()
                if now - conn.last_activity > self.timeout
            ]

            for conn_id in expired:
                conn = self._connections.pop(conn_id, None)
                if conn:
                    # 从 stream 索引中移除
                    if conn.stream_key in self._by_stream:
                        self._by_stream[conn.stream_key].discard(conn_id)

                    logger.warning(
                        f"SSE connection expired: {conn_id}, "
                        f"stream={conn.stream_key}, "
                        f"inactive={now - conn.last_activity:.1f}s"
                    )

            return len(expired)

    async def get_stats(self) -> dict:
        """获取连接统计。

        Returns:
            包含连接统计信息的字典
        """
        async with self._lock:
            now = time.time()
            return {
                "total_connections": len(self._connections),
                "by_stream": {
                    stream: len(conns)
                    for stream, conns in self._by_stream.items()
                },
                "oldest_connection": min(
                    (conn.created_at for conn in self._connections.values()),
                    default=now
                ),
            }


# 全局管理器实例
_manager: SSEConnectionManager | None = None


def get_sse_manager() -> SSEConnectionManager:
    """获取 SSE 连接管理器单例。

    Returns:
        SSE 连接管理器实例
    """
    global _manager
    if _manager is None:
        _manager = SSEConnectionManager()
    return _manager
"""测试 SSE 连接管理器。

验证连接追踪、活动更新、过期清理等功能。
"""
import asyncio
import pytest
from app.sse.manager import get_sse_manager, SSEConnectionManager


@pytest.mark.asyncio
async def test_sse_connection_manager_basic():
    """测试基本的连接管理功能。"""
    manager = SSEConnectionManager(timeout_seconds=60)

    # 注册连接
    await manager.register("conn-1", "workflow:123", "192.168.1.1")

    # 验证连接已注册
    stats = await manager.get_stats()
    assert stats["total_connections"] == 1
    assert "workflow:123" in stats["by_stream"]
    assert stats["by_stream"]["workflow:123"] == 1

    # 更新活动时间
    await manager.update_activity("conn-1")

    # 注销连接
    await manager.unregister("conn-1")

    # 验证连接已注销
    stats = await manager.get_stats()
    assert stats["total_connections"] == 0
    assert "workflow:123" not in stats["by_stream"]


@pytest.mark.asyncio
async def test_sse_connection_manager_multiple_streams():
    """测试多流连接管理。"""
    manager = SSEConnectionManager(timeout_seconds=60)

    # 注册多个连接
    await manager.register("conn-1", "workflow:123", "192.168.1.1")
    await manager.register("conn-2", "workflow:123", "192.168.1.2")
    await manager.register("conn-3", "parse:456", "192.168.1.3")

    # 验证统计信息
    stats = await manager.get_stats()
    assert stats["total_connections"] == 3
    assert stats["by_stream"]["workflow:123"] == 2
    assert stats["by_stream"]["parse:456"] == 1

    # 注销部分连接
    await manager.unregister("conn-2")

    # 验证统计信息更新
    stats = await manager.get_stats()
    assert stats["total_connections"] == 2
    assert stats["by_stream"]["workflow:123"] == 1

    # 清理
    await manager.unregister("conn-1")
    await manager.unregister("conn-3")


@pytest.mark.asyncio
async def test_sse_connection_manager_cleanup_expired():
    """测试过期连接清理。"""
    manager = SSEConnectionManager(timeout_seconds=1)  # 1 秒超时

    # 注册连接
    await manager.register("conn-1", "workflow:123", "192.168.1.1")
    await manager.register("conn-2", "parse:456", "192.168.1.2")

    # 等待超时
    await asyncio.sleep(1.5)

    # 清理过期连接
    cleaned = await manager.cleanup_expired()
    assert cleaned == 2

    # 验证连接已清理
    stats = await manager.get_stats()
    assert stats["total_connections"] == 0


@pytest.mark.asyncio
async def test_sse_connection_manager_singleton():
    """测试全局单例。"""
    manager1 = get_sse_manager()
    manager2 = get_sse_manager()

    # 验证是同一个实例
    assert manager1 is manager2


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
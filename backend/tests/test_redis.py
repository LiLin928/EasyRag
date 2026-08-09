"""Redis 连接单元测试。"""
import pytest

from app.db.redis import get_redis


@pytest.mark.asyncio
async def test_redis_ping():
    """连接 Redis 并 ping 成功（依赖 .env REDIS_URL 指向虚拟机 :6379）。"""
    r = await get_redis()
    assert await r.ping() is True

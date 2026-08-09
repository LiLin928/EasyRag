"""Redis 异步连接模块。"""
from redis.asyncio import Redis

from app.config import settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    """返回全局 Redis 连接（单例，首次调用时按 settings.redis_url 建立）。"""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis

"""分布式锁

基于 Redis 的分布式锁，用于防止任务重复执行。
"""
import asyncio
import uuid
import logging
from typing import Optional, Any
from contextlib import asynccontextmanager
from datetime import timedelta

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class DistributedLock:
    """
    分布式锁
    
    使用 Redis SETNX 实现
    
    示例:
        async with DistributedLock("doc:123:parse"):
            # 临界区代码
            await parse_document(doc_id)
    """
    
    def __init__(
        self,
        lock_key: str,
        lock_value: Optional[str] = None,
        ttl_seconds: int = 300,
        retry_interval: float = 0.1,
        max_retries: int = 100
    ):
        self.lock_key = f"lock:{lock_key}"
        self.lock_value = lock_value or str(uuid.uuid4())
        self.ttl = ttl_seconds
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self._redis: Optional[aioredis.Redis] = None
        self._locked = False
    
    async def _get_redis(self) -> aioredis.Redis:
        """获取 Redis 连接"""
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis
    
    async def acquire(self) -> bool:
        """
        获取锁
        
        Returns:
            True if acquired, False otherwise
        """
        redis = await self._get_redis()
        
        for attempt in range(self.max_retries):
            # SET key value NX EX seconds
            # NX: Only set if key does not exist
            # EX: Set expiry
            result = await redis.set(
                self.lock_key,
                self.lock_value,
                nx=True,
                ex=self.ttl
            )
            
            if result:
                self._locked = True
                logger.debug(f"Lock acquired: {self.lock_key}")
                return True
            
            # 等待重试
            await asyncio.sleep(self.retry_interval)
        
        logger.warning(f"Failed to acquire lock: {self.lock_key}")
        return False
    
    async def release(self):
        """释放锁"""
        if not self._locked:
            return
        
        redis = await self._get_redis()
        
        # 使用 Lua 脚本安全释放
        # 只释放自己持有的锁
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        result = await redis.eval(
            lua_script,
            1,  # key count
            self.lock_key,
            self.lock_value
        )
        
        if result:
            logger.debug(f"Lock released: {self.lock_key}")
        else:
            logger.warning(f"Lock release failed (not owner): {self.lock_key}")
        
        self._locked = False
    
    async def extend(self, additional_ttl: int) -> bool:
        """
        延长锁的过期时间
        
        Args:
            additional_ttl: 额外秒数
            
        Returns:
            True if extended
        """
        if not self._locked:
            return False
        
        redis = await self._get_redis()
        
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        
        result = await redis.eval(
            lua_script,
            1,
            self.lock_key,
            self.lock_value,
            str(self.ttl + additional_ttl)
        )
        
        return bool(result)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        acquired = await self.acquire()
        if not acquired:
            raise LockAcquisitionError(f"Failed to acquire lock: {self.lock_key}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.release()


class LockAcquisitionError(Exception):
    """锁获取失败异常"""
    pass


# 便捷函数
async def with_lock(
    lock_key: str,
    ttl_seconds: int = 300,
    max_retries: int = 100
):
    """
    便捷函数：使用锁执行代码
    
    示例:
        async with with_lock("doc:123:parse"):
            await parse_document(123)
    """
    return DistributedLock(lock_key, ttl_seconds=ttl_seconds, max_retries=max_retries)


class TaskLock:
    """
    任务锁装饰器
    
    防止任务重复执行
    
    示例:
        @TaskLock("doc:{doc_id}")
        def parse_document(self, doc_id: int):
            pass
    """
    
    def __init__(self, key_template: str, ttl_seconds: int = 300):
        self.key_template = key_template
        self.ttl = ttl_seconds
    
    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            # 解析锁 key
            lock_key = self._format_key(args, kwargs)
            
            async with DistributedLock(lock_key, ttl_seconds=self.ttl):
                return await func(*args, **kwargs)
        
        return wrapper
    
    def _format_key(self, args, kwargs) -> str:
        """格式化锁 key"""
        # 简化实现，实际应该根据函数签名解析
        return self.key_template


# 全局锁管理器
class LockManager:
    """锁管理器"""
    
    _locks: dict = {}
    
    @classmethod
    def get_lock(cls, key: str, **kwargs) -> DistributedLock:
        """获取或创建锁"""
        if key not in cls._locks:
            cls._locks[key] = DistributedLock(key, **kwargs)
        return cls._locks[key]
    
    @classmethod
    async def release_all(cls):
        """释放所有锁"""
        for key, lock in cls._locks.items():
            await lock.release()
        cls._locks.clear()
    
    @classmethod
    async def get_active_locks(cls) -> list:
        """获取所有活跃锁"""
        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        keys = await redis.keys("lock:*")
        await redis.close()
        return keys

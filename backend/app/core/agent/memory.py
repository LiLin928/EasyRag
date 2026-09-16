"""Agent 记忆：checkpoint 存储。

开发环境用 MemorySaver（进程内），生产环境用 AsyncPostgresSaver（持久化）。
单 worker 起步用 MemorySaver；横向扩展时切换 PostgresSaver（接口不变）。
"""
from app.config import settings
import logging

logger = logging.getLogger(__name__)

_checkpointer = None
_pool = None


async def get_checkpointer():
    """返回单例 checkpointer（首次调用时惰性创建）。

    生产环境使用 PostgresSaver（持久化）。
    开发环境使用 MemorySaver（简单、快速）。
    """
    global _checkpointer, _pool
    if _checkpointer is not None:
        return _checkpointer

    # 从配置判断是否使用持久化
    use_persistent = settings.workflow_persistent

    if use_persistent:
        # 生产环境：使用 PostgresSaver（持久化、多实例支持）
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from langgraph.checkpoint.postgres._ainternal import AsyncConnectionPool

            logger.info("[Checkpointer] Initializing PostgresSaver for persistent workflow...")

            # 转换数据库 URL（去掉 +asyncpg 后缀）
            db_url = settings.database_url
            if '+asyncpg' in db_url:
                db_url = db_url.replace('+asyncpg', '')

            # 创建连接池（使用正确的参数名）
            _pool = AsyncConnectionPool(
                db_url,
                max_size=10,
                kwargs={'autocommit': True}
            )

            # 初始化连接池
            await _pool.open()

            # 创建 PostgresSaver
            checkpointer = AsyncPostgresSaver(_pool)

            # 设置数据库表（创建 checkpoint 相关表）
            await checkpointer.setup()

            _checkpointer = checkpointer
            logger.info("[Checkpointer] PostgresSaver initialized with persistent support")

        except Exception as e:
            logger.error(f"[Checkpointer] Failed to initialize PostgresSaver: {e}", exc_info=True)
            logger.warning("[Checkpointer] Falling back to MemorySaver...")
            from langgraph.checkpoint.memory import MemorySaver
            _checkpointer = MemorySaver()
    else:
        # 开发环境：使用 MemorySaver
        from langgraph.checkpoint.memory import MemorySaver

        logger.info("[Checkpointer] Using MemorySaver for development")
        _checkpointer = MemorySaver()
        logger.info("[Checkpointer] MemorySaver initialized")

    return _checkpointer


async def init_checkpointer_for_worker():
    """ARQ worker startup 时提前初始化 checkpointer，避免首个任务冷启动。"""
    await get_checkpointer()


async def close_checkpointer():
    """关闭 checkpointer 和连接池（应用关闭时调用）。"""
    global _pool

    if _pool is not None:
        await _pool.close()
        logger.info("[Checkpointer] Connection pool closed")
"""Agent 记忆：checkpoint 存储。

开发环境用 MemorySaver（进程内），生产环境用 AsyncPostgresSaver（持久化）。
单 worker 起步用 MemorySaver；横向扩展时切换 PostgresSaver（接口不变）。
"""
from app.config import settings
from langgraph.checkpoint.memory import MemorySaver
import logging

logger = logging.getLogger(__name__)

_checkpointer = None


async def get_checkpointer():
    """返回单例 checkpointer（首次调用时惰性创建）。

    开发环境使用 MemorySaver（简单、无需额外依赖）。
    生产环境可切换为 PostgresSaver（需安装 langgraph-checkpoint-postgres）。
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    # 开发环境：使用 MemorySaver（简单、快速）
    logger.info("[Checkpointer] Using MemorySaver for development...")
    _checkpointer = MemorySaver()
    logger.info("[Checkpointer] MemorySaver initialized successfully")
    return _checkpointer


async def init_checkpointer_for_worker():
    """ARQ worker startup 时提前初始化 checkpointer，避免首个任务冷启动。"""
    await get_checkpointer()
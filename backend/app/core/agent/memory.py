"""Agent 记忆：checkpoint 存储。

开发环境用 MemorySaver（进程内），生产环境用 AsyncPostgresSaver（持久化）。
单 worker 起步用 MemorySaver；横向扩展时切换 PostgresSaver（接口不变）。
"""
from app.config import settings

_checkpointer = None


async def get_checkpointer():
    """返回单例 checkpointer（首次调用时惰性创建）。"""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    if settings.env == "production":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        cp = AsyncPostgresSaver.from_conn_string(settings.database_url)
        await cp.setup()
        _checkpointer = cp
    else:
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()
    return _checkpointer
 

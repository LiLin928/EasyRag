"""SSE 连接清理任务。

定时清理过期的 SSE 连接，防止资源泄漏。
"""
import logging

from celery import shared_task

from app.sse.manager import get_sse_manager
from app.worker.loop import get_worker_event_loop as _get_event_loop


logger = logging.getLogger(__name__)


@shared_task(name="sse.cleanup_expired")
def cleanup_expired_sse_connections():
    """定时清理过期的 SSE 连接。

    每 5 分钟执行一次，清理超过 5 分钟无活动的连接。
    """
    async def _cleanup():
        manager = get_sse_manager()
        cleaned = await manager.cleanup_expired()

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired SSE connections")
        else:
            logger.debug("No expired SSE connections to cleanup")

    # 使用持久事件循环
    loop = _get_event_loop()
    loop.run_until_complete(_cleanup())
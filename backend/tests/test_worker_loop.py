"""Worker 持久事件循环测试。

防止回归 asyncpg "attached to a different loop"：Celery 任务必须复用
同一持久事件循环，避免全局 async engine 连接池的连接被绑定到已关闭的循环。
"""
import asyncio


def test_worker_loop_singleton():
    """多次获取返回同一未关闭循环。"""
    from app.worker.loop import get_worker_event_loop

    a = get_worker_event_loop()
    b = get_worker_event_loop()
    assert a is b
    assert not a.is_closed()


def test_run_async_uses_persistent_loop():
    """_run_async 多次调用必须在同一事件循环上跑协程。

    修复前用 asyncio.run() 每次新建并关闭循环，会导致全局 engine 连接池
    的连接绑定到已关闭循环 → "attached to a different loop"。
    """
    from app.worker.tasks.parse_tasks import _run_async

    seen: dict = {}

    async def _capture():
        seen["loop"] = asyncio.get_running_loop()

    _run_async(_capture())
    first = seen.get("loop")
    _run_async(_capture())
    second = seen.get("loop")

    assert first is not None
    assert first is second, "两次 _run_async 跑在不同事件循环上"

"""Worker 进程级持久事件循环。

Celery 任务必须复用同一事件循环：全局异步 engine 的连接池会把 asyncpg
连接绑定到首次使用它的循环上。若每次任务都用 ``asyncio.run()`` 新建并关闭
循环，下次任务复用池中连接时便会报 ``attached to a different loop``
（连接绑定到已关闭的旧循环）。

本模块提供进程级单例循环，所有 Celery 任务通过 ``get_worker_event_loop``
复用同一循环，从根本上避免跨循环问题。
"""
import asyncio
import sys

_event_loop: asyncio.AbstractEventLoop | None = None


def get_worker_event_loop() -> asyncio.AbstractEventLoop:
    """获取或创建 worker 进程级持久事件循环。

    Returns:
        进程内唯一的事件循环实例（懒创建，复用至进程结束）。
    """
    global _event_loop
    # Windows 必须用 SelectorEventLoop，asyncpg/proactor 不兼容
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)
    return _event_loop

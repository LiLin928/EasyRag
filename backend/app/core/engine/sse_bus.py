"""SSE 事件总线：工作流执行进度推送。

单 worker 模式下直接 yield SSE 事件；
多 worker 模式下经 Redis pub/sub 分发（接口不变）。
"""
import asyncio
import json
from collections import defaultdict

from app.sse.emitter import sse_event

_queues: dict[str, list[asyncio.Queue]] = defaultdict(list)


def subscribe(execution_id: str) -> asyncio.Queue:
    """订阅指定执行的事件流，返回 Queue。"""
    q: asyncio.Queue = asyncio.Queue(maxsize=256)
    _queues[execution_id].append(q)
    return q


def unsubscribe(execution_id: str, queue: asyncio.Queue):
    """取消订阅。"""
    if execution_id in _queues:
        _queues[execution_id] = [q for q in _queues[execution_id] if q is not queue]
        if not _queues[execution_id]:
            del _queues[execution_id]


async def publish(execution_id: str, event: str, data: dict):
    """向所有订阅者推送事件。"""
    for q in _queues.get(execution_id, []):
        try:
            q.put_nowait(sse_event(event, data))
        except asyncio.QueueFull:
            pass


async def drain(queue: asyncio.Queue):
    """生成器：从队列消费 SSE 事件直到 None 哨兵。"""
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item
 

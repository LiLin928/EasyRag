"""SSE 事件总线：基于 Redis Stream 的工作流执行进度推送。

publish 写入 Redis Stream（XADD），subscribe 从 Stream 读取（XRANGE 历史回放 + XREAD 实时尾随）。
支持跨进程：ARQ worker publish，API 进程 subscribe。
"""
import json
from typing import AsyncGenerator

from app.db.redis import get_redis
from app.sse.emitter import sse_event

STREAM_KEY = "execution:{eid}"
MAXLEN = 500
# 终止事件名，subscribe 收到后停止读取
_TERMINAL_EVENTS = {"execution_complete", "error", "execution_cancelled", "execution_paused"}


async def publish(execution_id: str, event: str, data: dict) -> None:
    """向 Redis Stream 写入一条事件（XADD MAXLEN 500）。"""
    r = await get_redis()
    await r.xadd(
        STREAM_KEY.format(eid=execution_id),
        {"event": event, "data": json.dumps(data, ensure_ascii=False)},
        maxlen=MAXLEN,
    )


async def subscribe(execution_id: str) -> AsyncGenerator[str, None]:
    """订阅执行事件流：先 XRANGE 读历史，再 XREAD BLOCK 实时尾随。

    yield SSE 格式字符串。收到终止事件后停止。
    """
    r = await get_redis()
    key = STREAM_KEY.format(eid=execution_id)

    # 1. XRANGE 历史回放
    history = await r.xrange(key)
    for _id, fields in history:
        event = fields.get("event", "")
        data_raw = fields.get("data", "{}")
        try:
            data = json.loads(data_raw)
        except (json.JSONDecodeError, TypeError):
            data = {}
        yield sse_event(event, data)
        if event in _TERMINAL_EVENTS:
            return

    # 2. 记住最后一条 ID，从其后开始 XREAD
    last_id = history[-1][0] if history else "0-0"

    # 3. XREAD BLOCK 实时尾随
    while True:
        result = await r.xread({key: last_id}, block=0)
        if not result:
            continue
        for _key, messages in result.items():
            for msg_id, fields in messages:
                last_id = msg_id
                event = fields.get("event", "")
                data_raw = fields.get("data", "{}")
                try:
                    data = json.loads(data_raw)
                except (json.JSONDecodeError, TypeError):
                    data = {}
                yield sse_event(event, data)
                if event in _TERMINAL_EVENTS:
                    return

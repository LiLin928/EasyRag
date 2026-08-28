"""SSE 事件格式化工具。

统一 chat / agent / workflow 三处 SSE 的事件行格式：
``event: <name>\\ndata: <json>\\n\\n``
"""
import json


def sse_event(event: str, data: dict) -> str:
    """格式化单条 SSE 事件。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_data(data: dict) -> str:
    """格式化无事件名的 SSE 数据行（兼容纯 data 流）。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

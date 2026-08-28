"""Redis Stream SSE bus 单元测试。"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_publish_xadd_to_stream(monkeypatch):
    """publish 调用 XADD 写入 Redis Stream，key 为 execution:{eid}。"""
    fake_redis = AsyncMock()
    fake_redis.xadd = AsyncMock()
    monkeypatch.setattr("app.core.engine.sse_bus.get_redis", AsyncMock(return_value=fake_redis))

    from app.core.engine.sse_bus import publish

    await publish("exec-1", "node_start", {"nodeId": "llm_1"})

    fake_redis.xadd.assert_called_once()
    call_args = fake_redis.xadd.call_args
    assert call_args.args[0] == "execution:exec-1"
    assert call_args.kwargs.get("maxlen") == 500
    fields = call_args.args[1]
    assert fields["event"] == "node_start"
    assert json.loads(fields["data"])["nodeId"] == "llm_1"


@pytest.mark.asyncio
async def test_subscribe_yields_history_then_live(monkeypatch):
    """subscribe 先 XRANGE 读历史，再 XREAD 实时尾随，yield SSE 格式事件。"""
    fake_redis = AsyncMock()
    # XRANGE 返回两条历史事件
    fake_redis.xrange = AsyncMock(return_value=[
        ("0-1", {"event": "execution_start", "data": '{"total_nodes": 2}'}),
        ("0-2", {"event": "node_start", "data": '{"nodeId": "start"}'}),
    ])
    # XREAD 第一次返回一条实时事件，第二次返回 None（模拟流结束）
    xread_call_count = 0

    async def fake_xread(streams, block=None):
        nonlocal xread_call_count
        xread_call_count += 1
        if xread_call_count == 1:
            return {"execution:exec-1": [("0-3", {"event": "execution_complete", "data": '{"success": true}'})]}
        return None  # 模拟无更多事件

    fake_redis.xread = fake_xread
    monkeypatch.setattr("app.core.engine.sse_bus.get_redis", AsyncMock(return_value=fake_redis))

    from app.core.engine.sse_bus import subscribe

    events = []
    async for sse in subscribe("exec-1"):
        events.append(sse)
        if "execution_complete" in sse:
            break  # 终止事件后停止

    assert len(events) == 3
    assert "execution_start" in events[0]
    assert "node_start" in events[1]
    assert "execution_complete" in events[2]

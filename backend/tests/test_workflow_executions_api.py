"""工作流执行 + 执行流 API 测试。"""
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_execute_endpoint_returns_immediately(monkeypatch):
    """POST /workflows/:id/execute 立即返回 executionId，不阻塞。"""
    monkeypatch.setattr("app.api.v2.workflows.enqueue_workflow_task", AsyncMock(return_value="exec-99"))

    fake_wf = MagicMock()
    fake_wf.id = "wf-1"
    fake_wf.definition = {"nodes": [{"id": "s", "type": "start"}]}
    fake_wf.last_run = None

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=fake_wf)

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_session.commit = AsyncMock()
    fake_session_cm = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.v2.workflows.async_session", lambda: fake_session_cm)

    from app.api.v2.workflows import execute
    from app.schemas.workflow import ExecuteRequest

    result = await execute("wf-1", ExecuteRequest(inputs={"q": "hi"}), me=type("U", (), {"id": "user-1"})())

    assert "exec-99" in str(result)


@pytest.mark.asyncio
async def test_stream_endpoint_uses_redis_subscribe(monkeypatch):
    """GET /executions/:id/stream 使用 sse_bus.subscribe（Redis Stream）。"""
    fake_execution = MagicMock()
    fake_execution.id = "e-1"
    fake_execution.status = "running"
    fake_execution.duration_ms = None

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=fake_execution)

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_session_cm = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.v2.executions.async_session", lambda: fake_session_cm)

    async def fake_subscribe(eid):
        yield 'event: execution_start\ndata: {"total_nodes": 1}\n\n'
        yield 'event: execution_complete\ndata: {"success": true}\n\n'

    monkeypatch.setattr("app.api.v2.executions.subscribe", fake_subscribe)

    from app.api.v2.executions import stream

    response = await stream("e-1", me=type("U", (), {"id": "u"})())

    assert response.media_type == "text/event-stream"


@pytest.mark.asyncio
async def test_resume_enqueues_arq(monkeypatch):
    """POST /executions/:id/resume 入队 ARQ task。"""
    fake_execution = MagicMock()
    fake_execution.id = "e-2"
    fake_execution.status = "paused"
    fake_execution.workflow_id = "wf-2"
    fake_execution.inputs = {}

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=fake_execution)

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_session.commit = AsyncMock()
    fake_session_cm = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.v2.executions.async_session", lambda: fake_session_cm)

    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock()
    monkeypatch.setattr("app.api.v2.executions.create_pool", AsyncMock(return_value=fake_pool))

    from app.api.v2.executions import resume

    result = await resume("e-2", me=type("U", (), {"id": "u"})())
    fake_pool.enqueue_job.assert_called_once_with("execute_workflow_task", execution_id="e-2")


@pytest.mark.asyncio
async def test_cancel_only_updates_db(monkeypatch):
    """POST /executions/:id/cancel 只更新 DB status，不操作 sse_bus。"""
    fake_execution = MagicMock()
    fake_execution.id = "e-3"
    fake_execution.status = "running"

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=fake_execution)

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_session.commit = AsyncMock()
    fake_session_cm = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.v2.executions.async_session", lambda: fake_session_cm)

    from app.api.v2.executions import cancel

    result = await cancel("e-3", me=type("U", (), {"id": "u"})())
    assert fake_execution.status == "cancelled"

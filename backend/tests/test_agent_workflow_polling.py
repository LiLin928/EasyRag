"""Agent 工作流工具轮询测试。"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_workflow_tool_polls_until_completed(monkeypatch):
    """_workflow_tool 入队后轮询 DB，completed 时返回 outputs。"""
    from app.core.agent.tool_registry import _workflow_tool

    fake_wf = MagicMock()
    fake_wf.id = "wf-1"
    fake_wf.name = "my_workflow"
    fake_wf.description = "a test workflow"

    # Mock enqueue
    monkeypatch.setattr("app.core.agent.tool_registry.enqueue_workflow_task", AsyncMock(return_value="exec-1"))

    # Mock 轮询：第一次 running，第二次 completed
    call_count = 0

    class FakeExec:
        def __init__(self, status, outputs):
            self.status = status
            self.outputs = outputs

    async def fake_get_execution(eid):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return FakeExec("running", None)
        return FakeExec("completed", {"result": "done"})

    monkeypatch.setattr("app.core.agent.tool_registry._get_execution", fake_get_execution)
    monkeypatch.setattr("app.core.agent.tool_registry.asyncio.sleep", AsyncMock())

    tool = _workflow_tool(fake_wf)
    result = await tool.ainvoke({})

    assert result == '{"result": "done"}' or "done" in str(result)


@pytest.mark.asyncio
async def test_workflow_tool_timeout(monkeypatch):
    """轮询超时返回 '工作流执行超时'。"""
    from app.core.agent.tool_registry import _workflow_tool

    fake_wf = MagicMock()
    fake_wf.id = "wf-2"
    fake_wf.name = "slow_wf"
    fake_wf.description = ""

    monkeypatch.setattr("app.core.agent.tool_registry.enqueue_workflow_task", AsyncMock(return_value="exec-2"))

    class FakeExec:
        def __init__(self):
            self.status = "running"
            self.outputs = None

    monkeypatch.setattr("app.core.agent.tool_registry._get_execution", AsyncMock(return_value=FakeExec()))
    monkeypatch.setattr("app.core.agent.tool_registry.asyncio.sleep", AsyncMock())
    monkeypatch.setattr("app.core.agent.tool_registry.WORKFLOW_TIMEOUT_SECONDS", 3)

    tool = _workflow_tool(fake_wf)
    result = await tool.ainvoke({})

    assert "超时" in str(result)

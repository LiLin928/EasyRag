"""ARQ enqueue 工具函数单元测试。"""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_enqueue_creates_execution_and_job(monkeypatch):
    """enqueue_workflow_task 创建 WorkflowExecution 记录并入队 ARQ job。"""
    # Arrange: mock async_session 返回假 session
    fake_session_cm = AsyncMock()
    fake_session = AsyncMock()
    fake_session.add = lambda obj: setattr(obj, "id", "exec-123")
    fake_session.commit = AsyncMock()
    fake_session.refresh = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.core.engine.arq_client.async_session", lambda: fake_session_cm)

    # Mock create_pool + enqueue_job
    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock()
    monkeypatch.setattr("app.core.engine.arq_client.create_pool", AsyncMock(return_value=fake_pool))

    from app.core.engine.arq_client import enqueue_workflow_task

    # Act
    result = await enqueue_workflow_task("wf-1", {"q": "hello"}, "manual", "user-1")

    # Assert
    assert result == "exec-123"
    fake_pool.enqueue_job.assert_called_once_with(
        "execute_workflow_task", execution_id="exec-123"
    )
"""ARQ enqueue 工具函数单元测试。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_enqueue_creates_execution_and_job(monkeypatch):
    """enqueue_workflow_task 创建 WorkflowExecution 记录并入队 ARQ job。"""
    # Create a mock workflow
    fake_wf = MagicMock()
    fake_wf.id = "wf-1"
    fake_wf.current_version = 0
    fake_wf.definition = {"nodes": [], "edges": []}

    # Create a mock result that returns fake_wf from scalar_one_or_none
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=fake_wf)

    # Arrange: mock async_session returning fake session
    fake_session_cm = AsyncMock()
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_session.add = lambda obj: setattr(obj, "id", "exec-123")
    fake_session.commit = AsyncMock()
    fake_session.refresh = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.core.engine.arq_client.async_session", lambda: fake_session_cm)

    # Mock create_pool + enqueue_job
    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock()
    monkeypatch.setattr("app.core.engine.arq_client.create_pool", AsyncMock(return_value=fake_pool))

    from app.core.engine.arq_client import enqueue_workflow_task

    # Act
    result = await enqueue_workflow_task("wf-1", {"q": "hello"}, "manual", "user-1")

    # Assert
    assert result == "exec-123"
    fake_pool.enqueue_job.assert_called_once_with(
        "execute_workflow_task", execution_id="exec-123"
    )

"""Celery 优先级队列测试。"""
import pytest
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from app.core.engine.celery_client import enqueue_workflow_task


@pytest.fixture
def setup_mocks():
    """设置所有必要的 mock 对象。"""
    # 创建模拟的 workflow
    mock_workflow = MagicMock()
    mock_workflow.id = uuid.uuid4()
    mock_workflow.current_version = 1
    mock_workflow.definition = {"nodes": [], "edges": []}

    # 创建模拟的 version
    mock_version = MagicMock()
    mock_version.definition_snapshot = {"nodes": [{"id": "start"}], "edges": []}

    # 创建模拟的 execution
    mock_execution = MagicMock()
    mock_execution.id = uuid.uuid4()

    return {
        "workflow": mock_workflow,
        "version": mock_version,
        "execution": mock_execution,
    }


@pytest.mark.asyncio
async def test_high_priority_task(setup_mocks):
    """测试高优先级任务提交到 high 队列。"""
    with patch("app.core.engine.celery_client.async_session") as mock_session, \
         patch("app.core.engine.celery_client.celery_app") as mock_celery:

        # 模拟 async context manager
        mock_session_instance = AsyncMock()
        mock_session_instance.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: setup_mocks["workflow"]),
            MagicMock(scalar_one_or_none=lambda: setup_mocks["version"]),
        ]
        mock_session_instance.add = MagicMock()
        mock_session_instance.commit = AsyncMock()
        mock_session_instance.refresh = AsyncMock()

        class MockAsyncSessionContext:
            async def __aenter__(self):
                return mock_session_instance
            async def __aexit__(self, *args):
                pass

        mock_session.return_value = MockAsyncSessionContext()
        mock_celery.send_task = MagicMock()

        # 执行测试
        execution_id = await enqueue_workflow_task(
            workflow_id="test-workflow-id",
            inputs={"test": "data"},
            trigger="manual",
            user_id=str(uuid.uuid4()),  # 使用有效的 UUID 字符串
            priority=9,  # 高优先级
        )

        # 验证任务提交到正确队列
        call_args = mock_celery.send_task.call_args
        assert call_args.kwargs.get("queue") == "high"
        assert call_args.kwargs.get("priority") == 9


@pytest.mark.asyncio
async def test_medium_priority_task(setup_mocks):
    """测试中等优先级任务提交到 workflow 队列。"""
    with patch("app.core.engine.celery_client.async_session") as mock_session, \
         patch("app.core.engine.celery_client.celery_app") as mock_celery:

        # 模拟 async context manager
        mock_session_instance = AsyncMock()
        mock_session_instance.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: setup_mocks["workflow"]),
            MagicMock(scalar_one_or_none=lambda: setup_mocks["version"]),
        ]
        mock_session_instance.add = MagicMock()
        mock_session_instance.commit = AsyncMock()
        mock_session_instance.refresh = AsyncMock()

        class MockAsyncSessionContext:
            async def __aenter__(self):
                return mock_session_instance
            async def __aexit__(self, *args):
                pass

        mock_session.return_value = MockAsyncSessionContext()
        mock_celery.send_task = MagicMock()

        # 执行测试
        execution_id = await enqueue_workflow_task(
            workflow_id="test-workflow-id",
            inputs={"test": "data"},
            trigger="manual",
            user_id=str(uuid.uuid4()),  # 使用有效的 UUID 字符串
            priority=5,  # 中等优先级
        )

        # 验证任务提交到正确队列
        call_args = mock_celery.send_task.call_args
        assert call_args.kwargs.get("queue") == "workflow"
        assert call_args.kwargs.get("priority") == 5


@pytest.mark.asyncio
async def test_low_priority_task(setup_mocks):
    """测试低优先级任务提交到 low 队列。"""
    with patch("app.core.engine.celery_client.async_session") as mock_session, \
         patch("app.core.engine.celery_client.celery_app") as mock_celery:

        # 模拟 async context manager
        mock_session_instance = AsyncMock()
        mock_session_instance.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: setup_mocks["workflow"]),
            MagicMock(scalar_one_or_none=lambda: setup_mocks["version"]),
        ]
        mock_session_instance.add = MagicMock()
        mock_session_instance.commit = AsyncMock()
        mock_session_instance.refresh = AsyncMock()

        class MockAsyncSessionContext:
            async def __aenter__(self):
                return mock_session_instance
            async def __aexit__(self, *args):
                pass

        mock_session.return_value = MockAsyncSessionContext()
        mock_celery.send_task = MagicMock()

        # 执行测试
        execution_id = await enqueue_workflow_task(
            workflow_id="test-workflow-id",
            inputs={"test": "data"},
            trigger="manual",
            user_id=str(uuid.uuid4()),  # 使用有效的 UUID 字符串
            priority=1,  # 低优先级
        )

        # 验证任务提交到正确队列
        call_args = mock_celery.send_task.call_args
        assert call_args.kwargs.get("queue") == "low"
        assert call_args.kwargs.get("priority") == 1


@pytest.mark.asyncio
async def test_default_priority(setup_mocks):
    """测试默认优先级（无 priority 参数）。"""
    with patch("app.core.engine.celery_client.async_session") as mock_session, \
         patch("app.core.engine.celery_client.celery_app") as mock_celery:

        # 模拟 async context manager
        mock_session_instance = AsyncMock()
        mock_session_instance.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: setup_mocks["workflow"]),
            MagicMock(scalar_one_or_none=lambda: setup_mocks["version"]),
        ]
        mock_session_instance.add = MagicMock()
        mock_session_instance.commit = AsyncMock()
        mock_session_instance.refresh = AsyncMock()

        class MockAsyncSessionContext:
            async def __aenter__(self):
                return mock_session_instance
            async def __aexit__(self, *args):
                pass

        mock_session.return_value = MockAsyncSessionContext()
        mock_celery.send_task = MagicMock()

        # 执行测试（不指定 priority，应使用默认值 5）
        execution_id = await enqueue_workflow_task(
            workflow_id="test-workflow-id",
            inputs={"test": "data"},
            trigger="manual",
            user_id=str(uuid.uuid4()),  # 使用有效的 UUID 字符串
        )

        # 验证默认行为
        call_args = mock_celery.send_task.call_args
        assert call_args.kwargs.get("queue") == "workflow"
        assert call_args.kwargs.get("priority") == 5


@pytest.mark.asyncio
async def test_priority_boundary_high(setup_mocks):
    """测试优先级边界值（>= 7 为高优先级）。"""
    with patch("app.core.engine.celery_client.async_session") as mock_session, \
         patch("app.core.engine.celery_client.celery_app") as mock_celery:

        # 模拟 async context manager
        mock_session_instance = AsyncMock()
        mock_session_instance.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: setup_mocks["workflow"]),
            MagicMock(scalar_one_or_none=lambda: setup_mocks["version"]),
        ]
        mock_session_instance.add = MagicMock()
        mock_session_instance.commit = AsyncMock()
        mock_session_instance.refresh = AsyncMock()

        class MockAsyncSessionContext:
            async def __aenter__(self):
                return mock_session_instance
            async def __aexit__(self, *args):
                pass

        mock_session.return_value = MockAsyncSessionContext()
        mock_celery.send_task = MagicMock()

        # 测试优先级 7
        await enqueue_workflow_task(
            workflow_id="test-workflow-id",
            inputs={},
            trigger="manual",
            user_id=str(uuid.uuid4()),  # 使用有效的 UUID 字符串
            priority=7,
        )

        call_args = mock_celery.send_task.call_args
        assert call_args.kwargs.get("queue") == "high"


@pytest.mark.asyncio
async def test_priority_boundary_low(setup_mocks):
    """测试优先级边界值（< 3 为低优先级）。"""
    with patch("app.core.engine.celery_client.async_session") as mock_session, \
         patch("app.core.engine.celery_client.celery_app") as mock_celery:

        # 模拟 async context manager
        mock_session_instance = AsyncMock()
        mock_session_instance.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: setup_mocks["workflow"]),
            MagicMock(scalar_one_or_none=lambda: setup_mocks["version"]),
        ]
        mock_session_instance.add = MagicMock()
        mock_session_instance.commit = AsyncMock()
        mock_session_instance.refresh = AsyncMock()

        class MockAsyncSessionContext:
            async def __aenter__(self):
                return mock_session_instance
            async def __aexit__(self, *args):
                pass

        mock_session.return_value = MockAsyncSessionContext()
        mock_celery.send_task = MagicMock()

        # 测试优先级 2
        await enqueue_workflow_task(
            workflow_id="test-workflow-id",
            inputs={},
            trigger="manual",
            user_id=str(uuid.uuid4()),  # 使用有效的 UUID 字符串
            priority=2,
        )

        call_args = mock_celery.send_task.call_args
        assert call_args.kwargs.get("queue") == "low"


@pytest.mark.asyncio
async def test_invalid_priority():
    """测试无效优先级抛出异常。"""
    with pytest.raises(ValueError, match="priority 必须在 0-9"):
        await enqueue_workflow_task(
            workflow_id="test-id",
            inputs={},
            trigger="manual",
            user_id=None,
            priority=10
        )


@pytest.mark.asyncio
async def test_negative_priority():
    """测试负数优先级抛出异常。"""
    with pytest.raises(ValueError, match="priority 必须在 0-9"):
        await enqueue_workflow_task(
            workflow_id="test-id",
            inputs={},
            trigger="manual",
            user_id=None,
            priority=-1
        )


@pytest.mark.asyncio
async def test_workflow_not_found():
    """测试工作流不存在抛出异常。"""
    with patch("app.core.engine.celery_client.async_session") as mock_session:
        # 模拟 async context manager
        mock_session_instance = AsyncMock()
        mock_session_instance.execute.return_value = MagicMock(
            scalar_one_or_none=lambda: None
        )

        class MockAsyncSessionContext:
            async def __aenter__(self):
                return mock_session_instance
            async def __aexit__(self, *args):
                pass

        mock_session.return_value = MockAsyncSessionContext()

        # 执行测试
        with pytest.raises(ValueError, match="工作流不存在"):
            await enqueue_workflow_task(
                workflow_id="invalid-id",
                inputs={},
                trigger="manual",
                user_id=None,
                priority=5
            )
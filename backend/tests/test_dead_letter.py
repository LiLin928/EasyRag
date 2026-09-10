"""死信队列功能测试。

测试死信队列的核心功能，包括添加、重试、统计和 API 接口。
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from app.models.dead_letter import DeadLetterTaskModel, TaskStatus
from app.worker.tasks.dead_letter import DeadLetterQueue, DeadLetterTask


class TestDeadLetterCore:
    """测试死信队列核心功能。"""

    def test_task_status_enum_values(self):
        """测试任务状态枚举值正确。"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RETRIED.value == "retried"
        assert TaskStatus.IGNORED.value == "ignored"

    def test_dead_letter_task_to_dict(self):
        """测试死信任务转换为字典。"""
        task = DeadLetterTask(
            task_id="test-123",
            task_name="parse_document",
            args=("doc-1",),
            kwargs={"key": "value"},
            exception="test error",
            traceback="test traceback",
            timestamp=datetime(2026, 9, 10, 12, 0, 0),
            retry_count=3,
            max_retries=3
        )

        result = task.to_dict()

        assert result["task_id"] == "test-123"
        assert result["task_name"] == "parse_document"
        assert json.loads(result["args"]) == ["doc-1"]
        assert json.loads(result["kwargs"]) == {"key": "value"}
        assert result["exception"] == "test error"
        assert result["retry_count"] == 3

    def test_dead_letter_task_unserializable_args(self):
        """测试不可序列化参数的处理。"""

        class CustomObject:
            pass

        task = DeadLetterTask(
            task_id="test-456",
            task_name="test_task",
            args=(CustomObject(),),
            kwargs={"obj": CustomObject()},
            exception="test error",
            traceback="",
            timestamp=datetime.utcnow(),
            retry_count=1,
            max_retries=3
        )

        # 应该不会抛出异常
        result = task.to_dict()
        assert "args" in result
        assert "kwargs" in result


class TestDeadLetterQueueOperations:
    """测试死信队列操作。"""

    @pytest.mark.asyncio
    async def test_add_to_dlq_success(self):
        """测试成功添加任务到死信队列。"""
        # Mock 数据库会话（正确设置上下文管理器）
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("app.worker.tasks.dead_letter.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.worker.tasks.dead_letter.publish_event") as mock_publish:
                await DeadLetterQueue.add_to_dlq(
                    task_id="test-123",
                    task_name="parse_document",
                    args=("doc-1",),
                    kwargs={},
                    exception=ValueError("test error"),
                    traceback_str="test traceback",
                    retry_count=3,
                    max_retries=3
                )

                # 验证数据库操作被调用
                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()

                # 验证发布事件被调用
                mock_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_to_dlq_db_failure_no_publish(self):
        """测试数据库保存失败时不发布到 Streams。"""
        # Mock 数据库会话，使其抛出异常
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(side_effect=Exception("DB Error"))
        mock_session.__aexit__ = AsyncMock()

        with patch("app.worker.tasks.dead_letter.async_session", return_value=mock_session):
            with patch("app.worker.tasks.dead_letter.publish_event") as mock_publish:
                await DeadLetterQueue.add_to_dlq(
                    task_id="test-789",
                    task_name="test_task",
                    args=("test",),
                    kwargs={"key": "value"},
                    exception=Exception("Test exception"),
                    traceback_str="Test traceback",
                    retry_count=1,
                    max_retries=3
                )

                # 验证 publish_event 没有被调用
                mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_dlq_task_success(self):
        """测试手动重试死信任务成功。"""
        # 创建模拟任务
        mock_task = MagicMock(spec=DeadLetterTaskModel)
        mock_task.task_id = "test-456"
        mock_task.task_name = "parse_document"
        mock_task.args = ["doc-2"]  # JSONB 存储为列表
        mock_task.kwargs = {}
        mock_task.status = TaskStatus.PENDING.value
        mock_task.retried_at = None

        # Mock 数据库查询
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("app.worker.tasks.dead_letter.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.celery_app.celery_app") as mock_celery:
                mock_celery.send_task = MagicMock()

                success = await DeadLetterQueue.retry_dlq_task("test-456", str(uuid4()))

                assert success is True
                mock_celery.send_task.assert_called_once()

                # 验证状态更新
                assert mock_task.status == TaskStatus.RETRIED
                assert mock_task.retried_at is not None

    @pytest.mark.asyncio
    async def test_retry_dlq_task_not_found(self):
        """测试重试不存在的任务。"""
        # Mock 数据库查询返回 None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.worker.tasks.dead_letter.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            success = await DeadLetterQueue.retry_dlq_task("non-existent-id")

            assert success is False

    @pytest.mark.asyncio
    async def test_get_dlq_stats(self):
        """测试获取死信队列统计。"""
        # Mock 数据库查询结果
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 3

        mock_type_result = MagicMock()
        mock_type_result.all.return_value = [
            ("parse_document", 2),
            ("execute_workflow", 1)
        ]

        mock_recent_result = MagicMock()
        mock_recent_result.scalar.return_value = 2

        mock_session = AsyncMock()

        # 模拟三次不同的查询
        mock_session.execute = AsyncMock(side_effect=[
            mock_total_result,
            mock_type_result,
            mock_recent_result
        ])

        with patch("app.worker.tasks.dead_letter.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            stats = await DeadLetterQueue.get_dlq_stats()

            assert stats["total_failed"] == 3
            assert "parse_document" in stats["by_task_type"]
            assert stats["by_task_type"]["parse_document"] == 2
            assert stats["last_24h"] == 2


class TestDeadLetterAPI:
    """测试死信队列 API 接口。"""

    @pytest.mark.asyncio
    async def test_list_dlq_tasks_api(self, client, auth_headers):
        """测试列出死信任务 API。"""
        # Mock 数据库会话
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.api.v2.dead_letter.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            response = await client.get("/api/v2/dead-letter/tasks", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "data" in data

    @pytest.mark.asyncio
    async def test_retry_dlq_task_api_success(self, client, auth_headers):
        """测试重试死信任务 API 成功场景。"""
        with patch("app.worker.tasks.dead_letter.DeadLetterQueue.retry_dlq_task") as mock_retry:
            mock_retry.return_value = True

            response = await client.post(
                "/api/v2/dead-letter/tasks/test-123/retry",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "已重新提交" in data["data"]["message"]

    @pytest.mark.asyncio
    async def test_retry_dlq_task_api_failure(self, client, auth_headers):
        """测试重试死信任务 API 失败场景。"""
        with patch("app.worker.tasks.dead_letter.DeadLetterQueue.retry_dlq_task") as mock_retry:
            mock_retry.return_value = False

            response = await client.post(
                "/api/v2/dead-letter/tasks/test-123/retry",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] != 0
            assert "重试失败" in data["message"]

    @pytest.mark.asyncio
    async def test_ignore_dlq_task_api_success(self, client, auth_headers):
        """测试忽略死信任务 API 成功场景。"""
        # Mock 数据库会话
        mock_task = MagicMock(spec=DeadLetterTaskModel)
        mock_task.task_id = "test-123"
        mock_task.status = TaskStatus.PENDING.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock()
        mock_session.__aexit__ = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("app.api.v2.dead_letter.async_session", return_value=mock_session):
            response = await client.post(
                "/api/v2/dead-letter/tasks/test-123/ignore",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "已忽略" in data["data"]["message"]

    @pytest.mark.asyncio
    async def test_ignore_dlq_task_api_not_found(self, client, auth_headers):
        """测试忽略不存在的死信任务。"""
        # Mock 数据库会话返回 None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.api.v2.dead_letter.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            response = await client.post(
                "/api/v2/dead-letter/tasks/non-existent/ignore",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] != 0
            assert "不存在" in data["message"]

    @pytest.mark.asyncio
    async def test_get_dlq_stats_api(self, client, auth_headers):
        """测试获取死信队列统计 API。"""
        # Mock 数据库查询结果
        mock_total_result = MagicMock()
        mock_total_result.scalar.return_value = 5

        mock_status_result = MagicMock()
        mock_status_result.all.return_value = [
            ("pending", 3),
            ("retried", 2)
        ]

        mock_type_result = MagicMock()
        mock_type_result.all.return_value = [
            ("parse_document", 3),
            ("execute_workflow", 2)
        ]

        mock_recent_result = MagicMock()
        mock_recent_result.scalar.return_value = 2

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[
            mock_total_result,
            mock_status_result,
            mock_type_result,
            mock_recent_result
        ])

        with patch("app.api.v2.dead_letter.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            response = await client.get("/api/v2/dead-letter/stats", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["total"] == 5
            assert "by_status" in data["data"]
            assert "by_type" in data["data"]


class TestDeadLetterCeleryTasks:
    """测试 Celery 任务。"""

    def test_add_to_dlq_task_celery(self):
        """测试 Celery 任务添加死信任务。"""
        from app.worker.tasks.dead_letter import add_to_dlq_task

        # Mock 数据库会话和异步操作
        with patch("app.worker.tasks.dead_letter.async_session") as mock_session_ctx:
            mock_session_instance = AsyncMock()
            mock_session_instance.add = MagicMock()
            mock_session_instance.commit = AsyncMock()

            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            # 执行任务（创建新的事件循环）
            add_to_dlq_task(
                task_id="test-789",
                task_name="parse_document",
                args=["doc-1"],
                kwargs={},
                exception="test error",
                traceback="test traceback",
                retry_count=3,
                max_retries=3
            )

            # 验证数据库操作被调用
            mock_session_instance.add.assert_called_once()

    def test_monitor_dead_letter_queue(self):
        """测试监控任务。"""
        from app.worker.tasks.dead_letter import monitor_dead_letter_queue

        # Mock 统计函数和告警函数
        with patch("app.worker.tasks.dead_letter.DeadLetterQueue.get_dlq_stats") as mock_stats:
            with patch("app.worker.tasks.dead_letter._send_alert") as mock_alert:
                mock_stats.return_value = {
                    "total_failed": 2,
                    "by_task_type": {"parse_document": 2},
                    "last_24h": 1
                }

                # 执行监控任务
                monitor_dead_letter_queue()

                # 验证告警被发送
                mock_alert.assert_called_once()

    def test_cleanup_old_dlq_tasks(self):
        """测试清理过期任务。"""
        from app.worker.tasks.dead_letter import cleanup_old_dlq_tasks

        # Mock 数据库操作
        mock_result = MagicMock()
        mock_result.rowcount = 5

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("app.worker.tasks.dead_letter.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            # 执行清理任务
            cleanup_old_dlq_tasks(days=30)

            # 验证数据库操作被调用
            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()


class TestDeadLetterModel:
    """测试死信任务模型。"""

    def test_model_repr(self):
        """测试模型字符串表示。"""
        task = DeadLetterTaskModel(
            task_id="test-123",
            task_name="parse_document",
            exception="test error",
            retry_count=3,
            max_retries=3,
            status=TaskStatus.PENDING.value
        )

        repr_str = repr(task)
        assert "DeadLetterTask" in repr_str
        assert "parse_document" in repr_str
        assert "test-123" in repr_str

    def test_model_default_values(self):
        """测试模型默认值（仅验证字段存在）。"""
        task = DeadLetterTaskModel(
            task_id="test-456",
            task_name="test_task",
            exception="error"
        )

        # 验证字段存在（默认值由数据库服务器设置）
        assert hasattr(task, 'retry_count')
        assert hasattr(task, 'max_retries')
        assert hasattr(task, 'status')
        # 注意：在 Python 对象中，这些值可能是 None，
        # 因为它们由数据库服务器设置默认值
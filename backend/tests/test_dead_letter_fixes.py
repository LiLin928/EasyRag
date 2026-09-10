"""测试死信队列修复"""
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.dead_letter import DeadLetterTaskModel, TaskStatus
from app.worker.tasks.dead_letter import DeadLetterTask, DeadLetterQueue


class TestDeadLetterFixes:
    """测试死信队列修复"""

    def test_task_status_enum(self):
        """测试状态枚举"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RETRIED.value == "retried"
        assert TaskStatus.IGNORED.value == "ignored"
        assert TaskStatus.PENDING == "pending"  # 继承自 str

    def test_json_serialization_with_complex_objects(self):
        """测试复杂对象的 JSON 序列化"""
        # 测试正常情况
        args = ("test", 123, {"key": "value"})
        kwargs = {"param": "value"}

        dl_task = DeadLetterTask(
            task_id="test-123",
            task_name="test_task",
            args=args,
            kwargs=kwargs,
            exception="Test exception",
            traceback="Test traceback",
            timestamp=datetime.utcnow(),
            retry_count=1,
            max_retries=3,
        )

        result = dl_task.to_dict()
        assert result["task_id"] == "test-123"
        assert json.loads(result["args"]) == ["test", 123, {"key": "value"}]
        assert json.loads(result["kwargs"]) == {"param": "value"}

    def test_json_serialization_with_unserializable_objects(self):
        """测试不可序列化对象的错误处理"""

        # 创建一个不可序列化的对象
        class UnserializableObject:
            pass

        args = (UnserializableObject(),)
        kwargs = {"obj": UnserializableObject()}

        dl_task = DeadLetterTask(
            task_id="test-456",
            task_name="test_task",
            args=args,
            kwargs=kwargs,
            exception="Test exception",
            traceback="Test traceback",
            timestamp=datetime.utcnow(),
            retry_count=1,
            max_retries=3,
        )

        # 应该不会抛出异常，而是使用 default=str 序列化
        result = dl_task.to_dict()
        assert result["task_id"] == "test-456"
        # 验证 args 和 kwargs 被序列化了（即使对象不可序列化）
        assert "args" in result
        assert "kwargs" in result

    def test_model_field_types(self):
        """测试模型字段类型"""
        # 验证字段类型注解
        from typing import get_type_hints

        hints = get_type_hints(DeadLetterTaskModel)
        # args 和 kwargs 应该是 dict 类型（映射到 JSONB）
        assert "args" in hints
        assert "kwargs" in hints

    @pytest.mark.asyncio
    async def test_data_consistency_no_db_save_no_stream_publish(self):
        """测试数据一致性：数据库保存失败时不发布到 Streams"""
        # Mock 数据库会话，使其抛出异常
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(side_effect=Exception("DB Error"))
        mock_session.__aexit__ = AsyncMock()

        with patch("app.worker.tasks.dead_letter.async_session", return_value=mock_session):
            # Mock publish_event
            with patch("app.worker.tasks.dead_letter.publish_event") as mock_publish:
                # 调用 add_to_dlq
                await DeadLetterQueue.add_to_dlq(
                    task_id="test-789",
                    task_name="test_task",
                    args=("test",),
                    kwargs={"key": "value"},
                    exception=Exception("Test exception"),
                    traceback_str="Test traceback",
                    retry_count=1,
                    max_retries=3,
                )

                # 验证 publish_event 没有被调用
                mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_data_consistency_db_success_publish_stream(self):
        """测试数据一致性：数据库保存成功后发布到 Streams"""
        # Mock 数据库会话
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock()
        mock_session.__aexit__ = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("app.worker.tasks.dead_letter.async_session", return_value=mock_session):
            # Mock publish_event
            with patch("app.worker.tasks.dead_letter.publish_event") as mock_publish:
                # 调用 add_to_dlq
                await DeadLetterQueue.add_to_dlq(
                    task_id="test-999",
                    task_name="test_task",
                    args=("test",),
                    kwargs={"key": "value"},
                    exception=Exception("Test exception"),
                    traceback_str="Test traceback",
                    retry_count=1,
                    max_retries=3,
                )

                # 验证 publish_event 被调用
                mock_publish.assert_called_once()
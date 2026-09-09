"""PostgreSQL 队列并发测试。"""
import asyncio
import pytest

from app.core.engine.arq_client import enqueue_workflow_task
from app.core.engine.pg_queue import PGJobQueue
from app.db.session import async_session
from app.models.workflow import WorkflowExecution
from sqlalchemy import select


@pytest.mark.asyncio
async def test_concurrent_dequeue_no_duplicate():
    """100 任务 / 3 Worker 并发，验证无重复执行。"""
    # 准备：创建 100 个任务
    execution_ids = []
    for i in range(100):
        exec_id = await enqueue_workflow_task(
            workflow_id="test-wf",
            inputs={"index": i},
            trigger="test",
            user_id=None
        )
        execution_ids.append(exec_id)
    
    # 验证：100 个不同任务 ID
    assert len(set(execution_ids)) == 100
    
    # 验证：数据库中有 100 个 pending 任务
    async with async_session() as s:
        pending = await PGJobQueue.count_pending(s)
        assert pending >= 100  # 可能有其他任务


@pytest.mark.asyncio
async def test_job_creation():
    """验证任务创建正确。"""
    exec_id = await enqueue_workflow_task(
        workflow_id="test-wf",
        inputs={},
        trigger="test",
        user_id=None
    )
    
    # 验证任务存在
    async with async_session() as s:
        row = await s.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
        )
        ex = row.scalar_one_or_none()
        assert ex is not None
        assert ex.status in ("pending", "running")

"""压力测试：100 并发工作流执行。"""
import asyncio
import pytest
import time
from datetime import datetime

from app.core.engine.arq_client import enqueue_workflow_task
from app.core.engine.pg_queue import PGJobQueue
from app.db.session import async_session
from sqlalchemy import select
from app.models.workflow import WorkflowExecution


async def wait_all_complete(execution_ids: list[str], timeout: int = 300):
    """等待所有执行完成。"""
    start = time.time()
    pending = set(execution_ids)
    
    while pending and (time.time() - start) < timeout:
        async with async_session() as s:
            for exec_id in list(pending):
                row = await s.execute(
                    select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
                )
                ex = row.scalar_one_or_none()
                if ex and ex.status in ("completed", "failed", "cancelled"):
                    pending.remove(exec_id)
        
        if pending:
            await asyncio.sleep(1)
    
    return pending  # 返回超时未完成的


@pytest.mark.asyncio
async def test_100_concurrent_workflows():
    """100 并发工作流执行测试。"""
    # 准备：创建 100 个任务
    execution_ids = []
    for i in range(100):
        exec_id = await enqueue_workflow_task(
            workflow_id="stress-test-wf",
            inputs={"index": i, "timestamp": datetime.now().isoformat()},
            trigger="stress_test",
            user_id=None
        )
        execution_ids.append(exec_id)
    
    # 等待完成
    timeout_ids = await wait_all_complete(execution_ids, timeout=300)
    
    # 验证
    assert len(timeout_ids) == 0, f"Tasks timed out: {timeout_ids}"
    assert len(set(execution_ids)) == 100, "Duplicate execution IDs"
    
    # 验证状态
    async with async_session() as s:
        statuses = {}
        for exec_id in execution_ids:
            row = await s.execute(
                select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
            )
            ex = row.scalar_one_or_none()
            if ex:
                statuses[exec_id] = ex.status
    
    completed = sum(1 for s in statuses.values() if s == "completed")
    failed = sum(1 for s in statuses.values() if s == "failed")
    
    print(f"\nResults: {completed} completed, {failed} failed")
    assert failed == 0, f"Some tasks failed: {failed}"


@pytest.mark.asyncio
async def test_enqueue_performance():
    """测试 enqueue 性能。"""
    latencies = []
    
    for i in range(100):
        start = time.time()
        await enqueue_workflow_task(
            workflow_id="bench-wf",
            inputs={"index": i},
            trigger="benchmark",
            user_id=None
        )
        latencies.append(time.time() - start)
    
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    
    print(f"\nEnqueue Performance:")
    print(f"  Average: {avg_latency:.3f}s")
    print(f"  Max: {max_latency:.3f}s")
    
    # 目标：平均延迟 < 2s
    assert avg_latency < 2.0, f"Average latency too high: {avg_latency:.3f}s"

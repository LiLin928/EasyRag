"""PostgreSQL queue enqueue 工具函数：创建 execution 记录 + 入队 PG 队列任务。

Task 6 改造后，改用 PGJobQueue 替代 ARQ (Redis)。
"""
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import select

from app.db.session import async_session
from app.core.engine.pg_queue import PGJobQueue
from app.models.workflow import Workflow, WorkflowExecution, WorkflowVersion


async def enqueue_workflow_task(
    workflow_id: str,
    inputs: dict | None,
    trigger: str,
    user_id: str | None,
) -> str:
    """创建 WorkflowExecution 记录并入队 PG 任务，返回 execution_id。

    API 进程和 Agent tool_registry 共用此函数。
    
    Args:
        workflow_id: 工作流 ID
        inputs: 工作流输入参数
        trigger: 触发类型 (manual/api/webhook/chat/agent)
        user_id: 触发用户 ID
        
    Returns:
        execution_id: 执行记录 ID
    """
    # 加载 workflow + version 获取 definition
    async with async_session() as s:
        wf = (
            await s.execute(select(Workflow).where(Workflow.id == workflow_id))
        ).scalar_one_or_none()
        if not wf:
            raise ValueError(f"工作流不存在: {workflow_id}")

        version = wf.current_version
        definition = wf.definition or {}
        if version > 0:
            ver = (
                await s.execute(
                    select(WorkflowVersion)
                    .where(WorkflowVersion.workflow_id == wf.id)
                    .where(WorkflowVersion.version == version)
                )
            ).scalar_one_or_none()
            if ver:
                definition = ver.definition_snapshot or definition

        # 使用 PGJobQueue 入队任务
        # PGJobQueue.enqueue 是静态方法，会创建 WorkflowExecution 和 job_queue 记录
        exec_id = await PGJobQueue.enqueue(
            session=s,
            workflow_id=wf.id,
            inputs=inputs or {},
            trigger=trigger,
            user_id=user_id,
            priority=0
        )
        
        return exec_id

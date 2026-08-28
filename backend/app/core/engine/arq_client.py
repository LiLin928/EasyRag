"""ARQ enqueue 工具函数：创建 execution 记录 + 入队 ARQ 任务。"""
from datetime import datetime

from arq import create_pool
from sqlalchemy import select

from app.config import settings
from app.db.session import async_session
from app.models.workflow import Workflow, WorkflowExecution, WorkflowVersion


async def enqueue_workflow_task(
    workflow_id: str,
    inputs: dict | None,
    trigger: str,
    user_id: str | None,
) -> str:
    """创建 WorkflowExecution 记录并入队 ARQ 任务，返回 execution_id。

    API 进程和 Agent tool_registry 共用此函数。
    """
    # 1. 加载 workflow + version 获取 definition
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

        # 2. 创建 execution 记录
        execution = WorkflowExecution(
            workflow_id=wf.id,
            version=version,
            user_id=user_id,
            status="running",
            trigger_type=trigger,
            inputs=inputs or {},
            started_at=datetime.now(),
        )
        s.add(execution)
        await s.commit()
        await s.refresh(execution)
        exec_id = str(execution.id)

    # 3. 入队 ARQ 任务
    pool = await create_pool(settings.redis_url)
    await pool.enqueue_job("execute_workflow_task", execution_id=exec_id)
    return exec_id

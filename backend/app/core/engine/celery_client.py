"""Celery 任务入队工具函数：创建 execution 记录 + 提交 Celery 任务。

从 V1 (PGJobQueue) 迁移到 V2 (Celery + Redis Streams)。
"""
from datetime import datetime
from typing import Optional
import uuid

import structlog
from sqlalchemy import select

from app.db.session import async_session
from app.models.workflow import Workflow, WorkflowExecution, WorkflowVersion
from app.core.celery_app import celery_app

logger = structlog.get_logger()


async def enqueue_workflow_task(
    workflow_id: str,
    inputs: dict | None,
    trigger: str,
    user_id: str | None,
    priority: int = 5,
    debug: bool = False,
) -> str:
    """创建 WorkflowExecution 记录并提交 Celery 任务，返回 execution_id。

    API 进程和 Agent tool_registry 共用此函数。

    Args:
        workflow_id: 工作流 ID
        inputs: 工作流输入参数
        trigger: 触发类型 (manual/api/webhook/chat/agent)
        user_id: 触发用户 ID
        priority: 任务优先级（0-9，9最高，默认5）
                  >= 7: 高优先级队列，用于紧急任务
                  >= 3: 默认业务队列，用于常规任务
                  < 3:  低优先级队列，用于后台清理等
        debug: 是否调试模式（默认 False）

    Returns:
        execution_id: 执行记录 ID

    Raises:
        ValueError: priority 超出范围或工作流不存在
    """
    # 验证优先级范围
    if not 0 <= priority <= 9:
        raise ValueError(f"priority 必须在 0-9 范围内，当前值: {priority}")

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

        # 创建 WorkflowExecution 记录
        execution = WorkflowExecution(
            workflow_id=wf.id,
            inputs=inputs or {},
            trigger_type=trigger,
            user_id=uuid.UUID(user_id) if user_id else None,
            status="pending",
            version=version,
            started_at=datetime.utcnow(),
        )
        s.add(execution)

        try:
            await s.commit()
            await s.refresh(execution)

            execution_id = str(execution.id)

            # 根据优先级选择队列
            if priority >= 7:
                queue = "high"
            elif priority >= 3:
                queue = "workflow"  # 中等优先级使用业务队列
            else:
                queue = "low"

            # 提交 Celery 任务 (V2 方式)
            logger.info(
                "提交 Celery 任务",
                execution_id=execution_id,
                debug=debug,
                priority=priority,
                queue=queue,
            )
            celery_app.send_task(
                "execute_workflow",
                args=[execution_id, definition, inputs or {}],
                kwargs={"debug": debug},
                queue=queue,
                task_id=execution_id,  # 使用 execution_id 作为 task_id，便于追踪
                priority=priority,  # 传递优先级给 Celery
            )

            # 记录日志
            logger.info(
                "提交工作流任务",
                execution_id=execution_id,
                priority=priority,
                queue=queue,
                workflow_id=workflow_id,
                trigger=trigger,
            )

            return execution_id

        except Exception as exc:
            # 回滚事务，确保数据一致性
            await s.rollback()
            logger.error(
                "提交工作流任务失败",
                workflow_id=workflow_id,
                priority=priority,
                error=str(exc),
            )
            raise


# 保留向后兼容的别名
enqueue_task = enqueue_workflow_task
"""死信队列管理 API。

提供死信任务的查询、重试、忽略等功能。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.dead_letter import DeadLetterTaskModel, TaskStatus
from app.models.user import User
from app.worker.tasks.dead_letter import DeadLetterQueue
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


router = APIRouter(prefix="/dead-letter", tags=["dead-letter"])


class DeadLetterTaskOut(BaseModel):
    """死信任务输出模型。

    用于 API 响应的死信任务信息。
    """

    id: str
    task_id: str
    task_name: str
    exception: str
    traceback: Optional[str]
    retry_count: int
    max_retries: int
    status: str
    created_at: datetime
    retried_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("/tasks")
async def list_dlq_tasks(
    status: str = Query(None, description="状态过滤（pending/retried/ignored）"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    me: User = Depends(get_current_user)
):
    """列出死信任务。

    支持按状态过滤和分页查询。

    Args:
        status: 状态过滤（pending/retried/ignored），可选。
        limit: 返回数量，默认 50，最大 200。
        offset: 偏移量，默认 0。
        me: 当前登录用户。

    Returns:
        死信任务列表。
    """
    async with async_session() as session:
        query = select(DeadLetterTaskModel)

        if status:
            query = query.where(DeadLetterTaskModel.status == status)

        query = query.order_by(DeadLetterTaskModel.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await session.execute(query)
        tasks = result.scalars().all()

        return ok([
            DeadLetterTaskOut(
                id=str(t.id),
                task_id=t.task_id,
                task_name=t.task_name,
                exception=t.exception,
                traceback=t.traceback,
                retry_count=t.retry_count,
                max_retries=t.max_retries,
                status=t.status,
                created_at=t.created_at,
                retried_at=t.retried_at,
            ).model_dump()
            for t in tasks
        ])


@router.post("/tasks/{task_id}/retry")
async def retry_dlq_task(
    task_id: str,
    me: User = Depends(get_current_user)
):
    """重试死信任务。

    将指定的死信任务重新提交到 Celery 队列执行。

    Args:
        task_id: Celery 任务 ID。
        me: 当前登录用户。

    Returns:
        操作结果消息。

    Raises:
        HTTPException: 重试失败时抛出 400 错误。
    """
    success = await DeadLetterQueue.retry_dlq_task(task_id, str(me.id))

    if not success:
        raise HTTPException(status_code=400, detail="重试失败")

    return ok({"message": "任务已重新提交"})


@router.post("/tasks/{task_id}/ignore")
async def ignore_dlq_task(
    task_id: str,
    me: User = Depends(get_current_user)
):
    """忽略死信任务（标记为已处理）。

    将指定的死信任务标记为 IGNORED 状态，不再处理。

    Args:
        task_id: Celery 任务 ID。
        me: 当前登录用户。

    Returns:
        操作结果消息。

    Raises:
        HTTPException: 任务不存在时抛出 404 错误。
    """
    async with async_session() as session:
        result = await session.execute(
            select(DeadLetterTaskModel).where(DeadLetterTaskModel.task_id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        task.status = TaskStatus.IGNORED
        await session.commit()

    return ok({"message": "任务已忽略"})


@router.get("/stats")
async def get_dlq_stats(me: User = Depends(get_current_user)):
    """获取死信队列统计。

    返回死信队列的总数、按状态统计、按任务类型统计以及最近 24 小时的失败任务数。

    Args:
        me: 当前登录用户。

    Returns:
        统计信息字典，包含：
        - total: 总数
        - by_status: 按状态统计
        - by_type: 按任务类型统计
        - last_24h: 最近 24 小时的失败任务数
    """
    async with async_session() as session:
        # 总数
        total_result = await session.execute(
            select(func.count(DeadLetterTaskModel.id))
        )
        total = total_result.scalar()

        # 按状态统计
        status_result = await session.execute(
            select(
                DeadLetterTaskModel.status,
                func.count(DeadLetterTaskModel.id)
            )
            .group_by(DeadLetterTaskModel.status)
        )
        by_status = dict(status_result.all())

        # 按任务类型统计
        type_result = await session.execute(
            select(
                DeadLetterTaskModel.task_name,
                func.count(DeadLetterTaskModel.id)
            )
            .group_by(DeadLetterTaskModel.task_name)
        )
        by_type = dict(type_result.all())

        # 最近 24 小时
        from datetime import timedelta
        recent_result = await session.execute(
            select(func.count(DeadLetterTaskModel.id))
            .where(DeadLetterTaskModel.created_at >= datetime.utcnow() - timedelta(hours=24))
        )
        last_24h = recent_result.scalar()

    return ok({
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "last_24h": last_24h,
    })
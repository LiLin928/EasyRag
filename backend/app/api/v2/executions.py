"""executions 路由：执行历史 + SSE 流 + 调试控制。

stream 端点订阅 Redis Streams 实时推送工作流执行进度。
cancel / resume / debug 端点使用 Celery API 控制任务。
"""
import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.core.redis_streams import subscribe_events
from app.core.celery_app import celery_app
from app.exceptions import BizException, ErrorCode
from app.models.workflow import Workflow, WorkflowExecution
from app.schemas.workflow import map_exec_status, map_exec_trigger
from app.sse.emitter import sse_event

router = APIRouter(prefix="/executions", tags=["executions"])


def _exec_out(ex: WorkflowExecution, wf: Workflow | None = None) -> dict:
    """构造执行历史响应字典。"""
    return {
        "id": str(ex.id),
        "workflowId": str(ex.workflow_id),
        "workflowName": wf.name if wf else "",
        "status": map_exec_status(ex.status),
        "trigger": map_exec_trigger(ex.trigger_type),
        "startTime": ex.started_at.isoformat() if ex.started_at else "",
        "duration": ex.duration_ms,
        "nodeProgress": ex.node_progress or "",
    }


@router.get("")
async def list_(
    workflowId: str | None = None,
    limit: int = 20,
    me=Depends(get_current_user),
):
    """列出执行历史。"""
    async with async_session() as s:
        q = (
            select(WorkflowExecution, Workflow)
            .join(Workflow, WorkflowExecution.workflow_id == Workflow.id)
            .order_by(WorkflowExecution.created_at.desc())
            .limit(limit)
        )
        if workflowId:
            q = q.where(WorkflowExecution.workflow_id == workflowId)
        rows = (await s.execute(q)).all()
    return ok([_exec_out(ex, wf) for ex, wf in rows])


@router.get("/{eid}/stream")
async def stream(eid: str, me=Depends(get_current_user)):
    """订阅执行事件流（Redis Streams 版本）。

    使用 Redis Streams 实时推送，延迟 <10ms。
    """
    async def event_generator():
        try:
            async for stream, event in subscribe_events([f"workflow:{eid}"]):
                yield sse_event(event.event_type, event.payload)

                # 终止事件
                if event.event_type in ("execution_completed", "execution_failed", "execution_cancelled"):
                    break
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/{eid}/cancel")
async def cancel(eid: str, me=Depends(get_current_user)):
    """取消执行：撤销 Celery 任务 + 更新 DB 状态。"""
    from datetime import datetime

    async with async_session() as s:
        ex = (
            await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))
        ).scalar_one_or_none()
        if not ex:
            raise BizException(ErrorCode.NOT_FOUND, "执行记录不存在")
        if ex.status in ("completed", "failed", "cancelled"):
            raise BizException(ErrorCode.BAD_REQUEST, f"执行已{ex.status}，无法取消")

        # 更新 workflow_executions 状态
        ex.status = "cancelled"
        ex.completed_at = datetime.now()
        await s.commit()

    # 撤销 Celery 任务
    celery_app.control.revoke(eid, terminate=True, signal="SIGTERM")

    return ok({"success": True})


@router.post("/{eid}/pause")
async def pause(eid: str, me=Depends(get_current_user)):
    """暂停执行（高级功能，需要 Worker 支持）。"""
    async with async_session() as s:
        ex = (
            await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))
        ).scalar_one_or_none()
        if not ex:
            raise BizException(ErrorCode.NOT_FOUND, "执行记录不存在")
        if ex.status != "running":
            raise BizException(ErrorCode.BAD_REQUEST, "仅运行中的执行可暂停")

        ex.status = "paused"
        await s.commit()

    # 暂停 Celery 任务（需要自定义实现）
    # celery_app.control.revoke(eid, terminate=False, signal="SIGUSR1")

    return ok({"success": True})


@router.post("/{eid}/resume")
async def resume(eid: str, me=Depends(get_current_user)):
    """恢复暂停的执行（需要检查点支持）。"""
    async with async_session() as s:
        ex = (
            await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))
        ).scalar_one_or_none()
        if not ex:
            raise BizException(ErrorCode.NOT_FOUND, "执行记录不存在")
        if ex.status != "paused":
            raise BizException(ErrorCode.BAD_REQUEST, "仅暂停状态的执行可恢复")

        # 恢复：重新提交任务
        wf = (
            await s.execute(select(Workflow).where(Workflow.id == ex.workflow_id))
        ).scalar_one_or_none()

        if not wf:
            raise BizException(ErrorCode.NOT_FOUND, "工作流不存在")

        # 更新状态
        ex.status = "running"
        await s.commit()

        # 重新提交任务
        celery_app.send_task(
            "execute_workflow",
            args=[eid, wf.definition or {}, ex.inputs or {}],
            kwargs={"resume": True},
            queue="workflow",
            task_id=eid,
        )

    return ok({"success": True})


@router.get("/{eid}")
async def detail(eid: str, me=Depends(get_current_user)):
    """获取执行详情。"""
    async with async_session() as s:
        ex = (
            await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))
        ).scalar_one_or_none()
        if not ex:
            raise BizException(ErrorCode.NOT_FOUND, "执行记录不存在")

        wf = (
            await s.execute(select(Workflow).where(Workflow.id == ex.workflow_id))
        ).scalar_one_or_none()

    return ok(_exec_out(ex, wf))


@router.post("/{eid}/debug/continue")
async def debug_continue(eid: str, me=Depends(get_current_user)):
    """调试继续执行：从暂停点恢复执行到下一个中断点或完成。

    仅当执行状态为 paused 时可调用。
    """
    from app.core.celery_app import celery_app

    async with async_session() as s:
        # 1. 获取执行记录
        exec_record = (
            await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))
        ).scalar_one_or_none()
        if not exec_record:
            raise BizException(ErrorCode.NOT_FOUND, "执行记录不存在")

        # 2. 检查状态
        if exec_record.status != "paused":
            raise BizException(ErrorCode.BAD_REQUEST, f"执行状态为 {exec_record.status}，仅 paused 状态可继续")

        # 3. 获取工作流定义
        wf = (
            await s.execute(select(Workflow).where(Workflow.id == exec_record.workflow_id))
        ).scalar_one_or_none()
        if not wf:
            raise BizException(ErrorCode.NOT_FOUND, "工作流不存在")

        # 4. 更新状态为 running
        exec_record.status = "running"
        await s.commit()

        definition = wf.definition or {}

    # 5. 提交恢复任务
    celery_app.send_task(
        "resume_workflow_execution",
        args=[eid, definition, True],  # debug=True
        queue="workflow",
        task_id=f"resume-{eid}",
    )

    return ok({
        "success": True,
        "message": "已提交继续执行任务"
    })
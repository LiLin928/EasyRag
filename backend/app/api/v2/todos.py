"""todos 路由：工作流人工待办列表 + 提交/拒绝。

cd（是否已超时）与 deadline（剩余秒数）由 deadline 时间戳实时计算。
提交/拒绝后恢复暂停的工作流执行。
"""
import asyncio

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.workflow import WorkflowExecution, WorkflowTodo

router = APIRouter(prefix="/todos", tags=["todos"])


def _try_resume_workflow(execution_id, user_id):
    """恢复暂停的工作流执行（后台异步触发）。"""

    async def _resume():
        from app.core.engine.executor import execute_workflow
        from app.models.workflow import Workflow

        async with async_session() as s:
            ex = (
                await s.execute(
                    select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
                )
            ).scalar_one_or_none()
            if not ex or ex.status != "paused":
                return
            wf = (
                await s.execute(select(Workflow).where(Workflow.id == ex.workflow_id))
            ).scalar_one_or_none()
            if not wf:
                return
            ex.status = "running"
            await s.commit()
            inputs = ex.inputs or {}

        await execute_workflow(str(wf.id), inputs, trigger="manual", user_id=user_id)

    asyncio.create_task(_resume())


def _out(td: WorkflowTodo) -> dict:
    """构造待办响应字典，计算超时状态与剩余秒数。"""
    now = datetime.now()
    cd = None
    deadline_sec = None
    if td.deadline:
        cd = td.deadline < now
        deadline_sec = max(0, int((td.deadline - now).total_seconds()))
    return {
        "id": str(td.id),
        "title": td.title,
        "source": td.source or "",
        "status": td.status,
        "submittedAt": td.submitted_at.isoformat() if td.submitted_at else None,
        "cd": cd,
        "deadline": deadline_sec,
        "formSchema": td.form_schema or [],
        "formData": td.form_data,
    }


@router.get("")
async def list_(status: str | None = None, me=Depends(get_current_user)):
    """列出待办，可按 status 过滤。"""
    async with async_session() as s:
        q = select(WorkflowTodo).order_by(WorkflowTodo.created_at.desc())
        if status:
            q = q.where(WorkflowTodo.status == status)
        rows = (await s.execute(q)).scalars().all()
    return ok([_out(r) for r in rows])


@router.get("/{tid}")
async def detail(tid: str, me=Depends(get_current_user)):
    """获取待办详情。"""
    async with async_session() as s:
        td = (
            await s.execute(select(WorkflowTodo).where(WorkflowTodo.id == tid))
        ).scalar_one_or_none()
    if not td:
        raise BizException(ErrorCode.NOT_FOUND, "待办不存在")
    return ok(_out(td))


@router.post("/{tid}/submit")
async def submit(tid: str, body: dict, me=Depends(get_current_user)):
    """提交待办表单数据，状态改 done，并恢复暂停的工作流执行。"""
    async with async_session() as s:
        td = (
            await s.execute(select(WorkflowTodo).where(WorkflowTodo.id == tid))
        ).scalar_one_or_none()
        if not td:
            raise BizException(ErrorCode.NOT_FOUND, "待办不存在")
        td.form_data = body
        td.status = "done"
        td.submitted_at = datetime.now()
        await s.commit()
        await s.refresh(td)

    _try_resume_workflow(td.execution_id, me.id)

    return ok(_out(td))


@router.post("/{tid}/reject")
async def reject(tid: str, me=Depends(get_current_user)):
    """拒绝待办，状态改 rejected，并标记工作流执行为失败。"""
    async with async_session() as s:
        td = (
            await s.execute(select(WorkflowTodo).where(WorkflowTodo.id == tid))
        ).scalar_one_or_none()
        if not td:
            raise BizException(ErrorCode.NOT_FOUND, "待办不存在")
        td.status = "rejected"
        await s.commit()
        await s.refresh(td)

        # 标记关联的执行记录为失败
        ex = (
            await s.execute(
                select(WorkflowExecution).where(WorkflowExecution.id == td.execution_id)
            )
        ).scalar_one_or_none()
        if ex and ex.status == "paused":
            ex.status = "failed"
            ex.error = f"人工节点 {td.node_id} 被拒绝"
            ex.completed_at = datetime.now()
            await s.commit()

    return ok(_out(td))

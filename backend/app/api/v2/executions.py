"""executions 路由：执行历史 + SSE 流 + 调试控制。

SSE 流端点当前返回 stub 事件序列，待 LangGraph 引擎接入后替换。
"""
import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.workflow import Workflow, WorkflowExecution
from app.schemas.workflow import map_exec_status, map_exec_trigger

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


@router.post("/{eid}/cancel")
async def cancel(eid: str, me=Depends(get_current_user)):
    """取消执行（stub）。"""
    async with async_session() as s:
        ex = (
            await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))
        ).scalar_one_or_none()
        if not ex:
            raise BizException(ErrorCode.NOT_FOUND, "执行记录不存在")
        ex.status = "cancelled"
        ex.completed_at = __import__("datetime").datetime.now()
        await s.commit()
    return ok({"success": True})


@router.post("/{eid}/resume")
async def resume(eid: str, me=Depends(get_current_user)):
    """恢复暂停的执行（stub）。"""
    async with async_session() as s:
        ex = (
            await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))
        ).scalar_one_or_none()
        if not ex:
            raise BizException(ErrorCode.NOT_FOUND, "执行记录不存在")
        ex.status = "running"
        await s.commit()
    return ok({"success": True})


@router.post("/{eid}/debug/continue")
async def debug_continue(eid: str, me=Depends(get_current_user)):
    """调试模式继续执行（stub）。"""
    return ok({"success": True})


@router.post("/{eid}/debug/test-node")
async def debug_test_node(eid: str, me=Depends(get_current_user)):
    """调试模式单节点测试（stub）。"""
    return ok({"success": True, "output": "stub"})


@router.get("/{eid}/nodes/{node_id}")
async def node_detail(eid: str, node_id: str, me=Depends(get_current_user)):
    """获取执行中某节点的详情（stub）。"""
    return ok({"nodeId": node_id, "status": "idle", "output": None})


@router.get("/{eid}/stream")
async def stream(eid: str, me=Depends(get_current_user)):
    """SSE 执行事件流（stub — 返回完整事件序列后关闭）。"""

    async def event_gen():
        # TODO: 替换为 LangGraph 执行引擎实时事件
        yield f"data: {json.dumps({'event': 'execution_start', 'total_nodes': 0})}\n\n"
        await asyncio.sleep(0.05)
        yield f"data: {json.dumps({'event': 'execution_complete', 'success': True, 'total_duration_ms': 0})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
"""executions 路由：执行历史 + SSE 流 + 调试控制。

SSE 流端点当前返回 stub 事件序列，待 LangGraph 引擎接入后替换。
"""
import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.workflow import Workflow, WorkflowExecution
from app.schemas.workflow import map_exec_status, map_exec_trigger

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


@router.post("/{eid}/cancel")
async def cancel(eid: str, me=Depends(get_current_user)):
    """取消执行（stub）。"""
    async with async_session() as s:
        ex = (
            await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))
        ).scalar_one_or_none()
        if not ex:
            raise BizException(ErrorCode.NOT_FOUND, "执行记录不存在")
        ex.status = "cancelled"
        ex.completed_at = datetime.now()
        await s.commit()
    return ok({"success": True})


@router.post("/{eid}/resume")
async def resume(eid: str, me=Depends(get_current_user)):
    """恢复暂停的执行（stub）。"""
    async with async_session() as s:
        ex = (
            await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))
        ).scalar_one_or_none()
        if not ex:
            raise BizException(ErrorCode.NOT_FOUND, "执行记录不存在")
        ex.status = "running"
        await s.commit()
    return ok({"success": True})


@router.post("/{eid}/debug/continue")
async def debug_continue(eid: str, me=Depends(get_current_user)):
    """调试模式继续执行（stub）。"""
    return ok({"success": True})


@router.post("/{eid}/debug/test-node")
async def debug_test_node(eid: str, me=Depends(get_current_user)):
    """调试模式单节点测试（stub）。"""
    return ok({"success": True, "output": "stub"})


@router.get("/{eid}/nodes/{node_id}")
async def node_detail(eid: str, node_id: str, me=Depends(get_current_user)):
    """获取执行中某节点的详情（stub）。"""
    return ok({"nodeId": node_id, "status": "idle", "output": None})


@router.get("/{eid}/stream")
async def stream(eid: str, me=Depends(get_current_user)):
    """SSE 执行事件流（stub — 返回完整事件序列后关闭）。"""

    async def event_gen():
        # TODO: 替换为 LangGraph 执行引擎实时事件
        yield f"data: {json.dumps({'event': 'execution_start', 'total_nodes': 0})}\n\n"
        await asyncio.sleep(0.05)
        yield f"data: {json.dumps({'event': 'execution_complete', 'success': True, 'total_duration_ms': 0})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")

"""workflows 路由：/workflows CRUD + 发布 + 复制 + 执行。

definition JSONB 存储 {nodes, edges}，_out 解包后返回前端。
执行端点创建 execution 记录并返回 executionId（实际 LangGraph 引擎待实现）。
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.workflow import Workflow, WorkflowExecution, WorkflowVersion
from app.schemas.workflow import ExecuteRequest, WorkflowCreate, WorkflowUpdate

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _out(wf: Workflow) -> dict:
    """构造工作流响应字典，从 definition 解包 nodes/edges。"""
    definition = wf.definition or {}
    return {
        "id": str(wf.id),
        "name": wf.name,
        "description": wf.description or "",
        "status": wf.status,
        "version": wf.current_version,
        "icon": wf.icon,
        "nodes": definition.get("nodes", []),
        "edges": definition.get("edges", []),
        "successRate": wf.success_rate,
        "lastRun": wf.last_run.isoformat() if wf.last_run else None,
        "createdAt": wf.created_at.isoformat() if wf.created_at else "",
        "updatedAt": wf.updated_at.isoformat() if wf.updated_at else "",
    }


@router.get("")
async def list_(me=Depends(get_current_user)):
    """列出当前用户的工作流。"""
    async with async_session() as s:
        rows = (
            await s.execute(
                select(Workflow)
                .where(Workflow.user_id == me.id)
                .order_by(Workflow.created_at.desc())
            )
        ).scalars().all()
    return ok([_out(r) for r in rows])


@router.post("")
async def create(body: WorkflowCreate, me=Depends(get_current_user)):
    """新建工作流（draft，空定义）。"""
    wf = Workflow(
        user_id=me.id,
        name=body.name,
        description=body.description,
        status="draft",
        definition={"nodes": [], "edges": []},
    )
    async with async_session() as s:
        s.add(wf)
        await s.commit()
        await s.refresh(wf)
    return ok(_out(wf))


@router.get("/{wid}")
async def detail(wid: str, me=Depends(get_current_user)):
    """获取工作流详情。"""
    async with async_session() as s:
        wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one_or_none()
    if not wf:
        raise BizException(ErrorCode.NOT_FOUND, "工作流不存在")
    return ok(_out(wf))


@router.put("/{wid}")
async def update(wid: str, body: WorkflowUpdate, me=Depends(get_current_user)):
    """更新工作流定义。"""
    async with async_session() as s:
        wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one_or_none()
        if not wf:
            raise BizException(ErrorCode.NOT_FOUND, "工作流不存在")
        if body.name is not None:
            wf.name = body.name
        if body.description is not None:
            wf.description = body.description
        if body.status is not None:
            wf.status = body.status
        if body.icon is not None:
            wf.icon = body.icon
        if body.version is not None:
            wf.current_version = body.version
        definition = wf.definition or {"nodes": [], "edges": []}
        if body.nodes is not None:
            definition["nodes"] = body.nodes
        if body.edges is not None:
            definition["edges"] = body.edges
        wf.definition = definition
        await s.commit()
        await s.refresh(wf)
    return ok(_out(wf))


@router.delete("/{wid}")
async def delete(wid: str, me=Depends(get_current_user)):
    """删除工作流。"""
    async with async_session() as s:
        wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one_or_none()
        if not wf:
            raise BizException(ErrorCode.NOT_FOUND, "工作流不存在")
        await s.delete(wf)
        await s.commit()
    return ok({"success": True})


@router.post("/{wid}/publish")
async def publish(wid: str, me=Depends(get_current_user)):
    """发布工作流：状态改 published，创建版本快照。"""
    async with async_session() as s:
        wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one_or_none()
        if not wf:
            raise BizException(ErrorCode.NOT_FOUND, "工作流不存在")
        new_version = wf.current_version + 1
        wf.status = "published"
        wf.current_version = new_version
        ver = WorkflowVersion(
            workflow_id=wf.id,
            version=new_version,
            definition_snapshot=wf.definition or {},
            published_at=datetime.now(),
        )
        s.add(ver)
        await s.commit()
        await s.refresh(wf)
    return ok(_out(wf))


@router.post("/{wid}/duplicate")
async def duplicate(wid: str, me=Depends(get_current_user)):
    """复制工作流（副本为 draft，版本归零）。"""
    async with async_session() as s:
        src = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one_or_none()
        if not src:
            raise BizException(ErrorCode.NOT_FOUND, "工作流不存在")
        dup = Workflow(
            user_id=me.id,
            name=src.name + " (副本)",
            description=src.description,
            status="draft",
            icon=src.icon,
            definition=src.definition,
        )
        s.add(dup)
        await s.commit()
        await s.refresh(dup)
    return ok(_out(dup))


@router.post("/{wid}/execute")
async def execute(wid: str, body: ExecuteRequest, me=Depends(get_current_user)):
    """触发工作流执行（stub — 创建 execution 记录，返回 executionId）。"""
    async with async_session() as s:
        wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one_or_none()
        if not wf:
            raise BizException(ErrorCode.NOT_FOUND, "工作流不存在")
        execution = WorkflowExecution(
            workflow_id=wf.id,
            version=wf.current_version,
            user_id=me.id,
            status="pending",
            trigger_type="manual",
            started_at=datetime.now(),
        )
        s.add(execution)
        await s.commit()
        await s.refresh(execution)
    # TODO: 启动 LangGraph 执行引擎
    return ok({"executionId": str(execution.id)})

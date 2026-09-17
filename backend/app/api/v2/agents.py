"""agents 路由：/agents CRUD。"""
from datetime import datetime

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user, require_roles
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])


def _out(a: Agent) -> dict:
    """构造智能体响应字典。"""
    return {
        "id": str(a.id),
        "name": a.name,
        "desc": a.description or "",
        "model": a.model,
        "prompt": a.prompt or "",
        "temp": a.temp,
        "maxtok": a.maxtok,
        "tools": a.tools or [],
        "docs": a.docs or [],
        "wfs": a.wfs or [],
        "mcps": a.mcps or [],
        "skills": a.skills or [],
        "enabled": a.enabled,
        "lastActive": a.last_active.isoformat() if a.last_active else "",
        "createdAt": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("")
async def list_(me=Depends(get_current_user)):
    """列出所有智能体。"""
    async with async_session() as s:
        rows = (await s.execute(select(Agent).order_by(Agent.created_at.desc()))).scalars().all()
    return ok([_out(r) for r in rows])


@router.post("")
async def create(body: AgentCreate, me=Depends(require_roles("admin"))):
    """新建智能体。"""
    a = Agent(
        name=body.name,
        description=body.desc,
        model=body.model,
        prompt=body.prompt,
        temp=body.temp,
        maxtok=body.maxtok,
        tools=body.tools,
        docs=body.docs,
        wfs=body.wfs,
        mcps=body.mcps,
        skills=body.skills,
        enabled=body.enabled,
    )
    async with async_session() as s:
        s.add(a)
        await s.commit()
        await s.refresh(a)
    return ok(_out(a))


@router.get("/{aid}")
async def detail(aid: str, me=Depends(get_current_user)):
    """获取智能体详情。"""
    async with async_session() as s:
        a = (await s.execute(select(Agent).where(Agent.id == aid))).scalar_one_or_none()
    if not a:
        raise BizException(ErrorCode.NOT_FOUND, "智能体不存在")
    return ok(_out(a))


@router.put("/{aid}")
async def update(aid: str, body: AgentUpdate, me=Depends(require_roles("admin"))):
    """更新智能体。"""
    async with async_session() as s:
        a = (await s.execute(select(Agent).where(Agent.id == aid))).scalar_one_or_none()
        if not a:
            raise BizException(ErrorCode.NOT_FOUND, "智能体不存在")
        for field, attr in [
            ("name", "name"), ("desc", "description"), ("model", "model"),
            ("prompt", "prompt"), ("temp", "temp"), ("maxtok", "maxtok"),
            ("tools", "tools"), ("docs", "docs"), ("wfs", "wfs"),
            ("mcps", "mcps"), ("skills", "skills"), ("enabled", "enabled"),
        ]:
            val = getattr(body, field)
            if val is not None:
                setattr(a, attr, val)
        a.last_active = datetime.now()
        await s.commit()
        await s.refresh(a)
    return ok(_out(a))


@router.delete("/{aid}")
async def delete(aid: str, me=Depends(require_roles("admin"))):
    """删除智能体。"""
    async with async_session() as s:
        a = (await s.execute(select(Agent).where(Agent.id == aid))).scalar_one_or_none()
        if not a:
            raise BizException(ErrorCode.NOT_FOUND, "智能体不存在")
        await s.delete(a)
    await s.commit()
    return ok({"success": True})


@router.post("/{aid}/chat")
async def chat(aid: str, body: dict = Body(default={}), me=Depends(get_current_user)):
    """智能体对话 SSE 流。"""
    from app.services.agent_service import AgentService
    svc = AgentService()

    async def gen():
        try:
            async for ev in svc.chat(aid, body.get("question", ""), me.id):
                yield ev
        except Exception as e:
            from app.sse.emitter import sse_event
            yield sse_event("error", {"code": 50001, "message": str(e)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/{aid}/history")
async def clear_history(aid: str, me=Depends(get_current_user)):
    """清除智能体对话历史记录。

    用于重置对话状态，清除累积的历史消息和失败的工具调用记录。
    """
    from app.core.agent.memory import get_checkpointer

    try:
        checkpointer = await get_checkpointer()

        # 构造 thread_id（与 agent_service.py 中的格式一致）
        thread_id = f"agent:{aid}:{me.id}"

        # 删除该 thread_id 的所有 checkpoint
        # LangGraph checkpointer 使用 adelete_thread 方法
        if hasattr(checkpointer, 'adelete_thread'):
            # MemorySaver 和 PostgresSaver 都支持
            await checkpointer.adelete_thread(thread_id)
        elif hasattr(checkpointer, 'storage'):
            # 备用方案：直接清空内存（仅 MemorySaver）
            if thread_id in checkpointer.storage:
                del checkpointer.storage[thread_id]

        return ok({"message": "历史记录已清除", "threadId": thread_id})

    except Exception as e:
        from app.exceptions import BizException, ErrorCode
        raise BizException(ErrorCode.SERVER_ERROR, f"清除历史记录失败: {str(e)}")

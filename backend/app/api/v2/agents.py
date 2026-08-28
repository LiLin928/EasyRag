"""agents 路由：/agents CRUD。"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_current_user
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
async def create(body: AgentCreate, me=Depends(get_current_user)):
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
async def update(aid: str, body: AgentUpdate, me=Depends(get_current_user)):
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
async def delete(aid: str, me=Depends(get_current_user)):
    """删除智能体。"""
    async with async_session() as s:
        a = (await s.execute(select(Agent).where(Agent.id == aid))).scalar_one_or_none()
        if not a:
            raise BizException(ErrorCode.NOT_FOUND, "智能体不存在")
        await s.delete(a)
        await s.commit()
    return ok({"success": True})

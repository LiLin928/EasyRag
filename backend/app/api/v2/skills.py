"""skills 路由：/skills CRUD + 复制。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.skill import Skill
from app.schemas.skill import SkillCreate, SkillUpdate

router = APIRouter(prefix="/skills", tags=["skills"])


def _out(s: Skill) -> dict:
    """构造技能响应字典。"""
    return {
        "id": str(s.id),
        "ico": s.icon,
        "name": s.name,
        "scope": s.scope,
        "ver": s.version,
        "desc": s.description or "",
        "trigger": s.trigger or "",
        "prompt": s.prompt or "",
        "tools": s.tools or [],
        "docs": s.docs or [],
        "wfs": s.wfs or [],
        "examples": s.examples or [],
        "scripts": s.scripts or [],
        "budget": s.budget,
        "used": s.used,
    }


@router.get("")
async def list_(me=Depends(get_current_user)):
    """列出所有技能。"""
    async with async_session() as s:
        rows = (await s.execute(select(Skill).order_by(Skill.created_at.desc()))).scalars().all()
    return ok([_out(r) for r in rows])


@router.post("")
async def create(body: SkillCreate, me=Depends(get_current_user)):
    """新建技能。"""
    sk = Skill(
        icon=body.ico,
        name=body.name,
        scope=body.scope,
        version=body.ver,
        description=body.desc,
        trigger=body.trigger,
        prompt=body.prompt,
        tools=body.tools,
        docs=body.docs,
        wfs=body.wfs,
        examples=[e.model_dump() for e in body.examples],
        scripts=[sc.model_dump() for sc in body.scripts],
        budget=body.budget,
    )
    async with async_session() as s:
        s.add(sk)
        await s.commit()
        await s.refresh(sk)
    return ok(_out(sk))


@router.get("/{sid}")
async def detail(sid: str, me=Depends(get_current_user)):
    """获取技能详情。"""
    async with async_session() as s:
        sk = (await s.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
    if not sk:
        raise BizException(ErrorCode.NOT_FOUND, "技能不存在")
    return ok(_out(sk))


@router.put("/{sid}")
async def update(sid: str, body: SkillUpdate, me=Depends(get_current_user)):
    """更新技能。"""
    async with async_session() as s:
        sk = (await s.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
        if not sk:
            raise BizException(ErrorCode.NOT_FOUND, "技能不存在")
        for field, attr in [
            ("ico", "icon"), ("name", "name"), ("scope", "scope"), ("ver", "version"),
            ("desc", "description"), ("trigger", "trigger"), ("prompt", "prompt"),
            ("tools", "tools"), ("docs", "docs"), ("wfs", "wfs"),
            ("budget", "budget"),
        ]:
            val = getattr(body, field)
            if val is not None:
                setattr(sk, attr, val)
        if body.examples is not None:
            sk.examples = [e.model_dump() for e in body.examples]
        if body.scripts is not None:
            sk.scripts = [sc.model_dump() for sc in body.scripts]
        await s.commit()
        await s.refresh(sk)
    return ok(_out(sk))


@router.delete("/{sid}")
async def delete(sid: str, me=Depends(get_current_user)):
    """删除技能。"""
    async with async_session() as s:
        sk = (await s.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
        if not sk:
            raise BizException(ErrorCode.NOT_FOUND, "技能不存在")
        await s.delete(sk)
        await s.commit()
    return ok({"success": True})


@router.post("/{sid}/duplicate")
async def duplicate(sid: str, me=Depends(get_current_user)):
    """复制技能（副本 scope 为 custom，used 归零）。"""
    async with async_session() as s:
        src = (await s.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
        if not src:
            raise BizException(ErrorCode.NOT_FOUND, "技能不存在")
        dup = Skill(
            icon=src.icon,
            name=src.name + " (副本)",
            scope="custom",
            version=src.version,
            description=src.description,
            trigger=src.trigger,
            prompt=src.prompt,
            tools=src.tools,
            docs=src.docs,
            wfs=src.wfs,
            examples=src.examples,
            scripts=src.scripts,
            budget=src.budget,
            used=0,
        )
        s.add(dup)
        await s.commit()
        await s.refresh(dup)
    return ok(_out(dup))

"""mcps 路由：/mcps CRUD + 测试。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.mcp import Mcp
from app.schemas.mcp import McpCreate, McpUpdate

router = APIRouter(prefix="/mcps", tags=["mcps"])


def _out(m: Mcp) -> dict:
    """构造 MCP 响应字典。"""
    return {
        "id": str(m.id),
        "name": m.name,
        "tp": m.tp,
        "cmd": m.cmd or "",
        "status": m.status,
        "toolCount": m.tool_count,
        "env": m.env or [],
        "timeout": m.timeout,
        "createdAt": m.created_at.isoformat() if m.created_at else None,
    }


@router.get("")
async def list_(me=Depends(get_current_user)):
    """列出所有 MCP 服务。"""
    async with async_session() as s:
        rows = (await s.execute(select(Mcp).order_by(Mcp.created_at.desc()))).scalars().all()
    return ok([_out(r) for r in rows])


@router.post("")
async def create(body: McpCreate, me=Depends(get_current_user)):
    """新建 MCP 服务。"""
    m = Mcp(
        name=body.name,
        tp=body.tp,
        cmd=body.cmd,
        status=body.status,
        tool_count=body.toolCount,
        env=[e.model_dump() for e in body.env],
        timeout=body.timeout,
    )
    async with async_session() as s:
        s.add(m)
        await s.commit()
        await s.refresh(m)
    return ok(_out(m))


@router.get("/{mid}")
async def detail(mid: str, me=Depends(get_current_user)):
    """获取 MCP 服务详情。"""
    async with async_session() as s:
        m = (await s.execute(select(Mcp).where(Mcp.id == mid))).scalar_one_or_none()
    if not m:
        raise BizException(ErrorCode.NOT_FOUND, "MCP 服务不存在")
    return ok(_out(m))


@router.put("/{mid}")
async def update(mid: str, body: McpUpdate, me=Depends(get_current_user)):
    """更新 MCP 服务。"""
    async with async_session() as s:
        m = (await s.execute(select(Mcp).where(Mcp.id == mid))).scalar_one_or_none()
        if not m:
            raise BizException(ErrorCode.NOT_FOUND, "MCP 服务不存在")
        for field, attr in [
            ("name", "name"), ("tp", "tp"), ("cmd", "cmd"), ("status", "status"),
            ("toolCount", "tool_count"), ("timeout", "timeout"),
        ]:
            val = getattr(body, field)
            if val is not None:
                setattr(m, attr, val)
        if body.env is not None:
            m.env = [e.model_dump() for e in body.env]
        await s.commit()
        await s.refresh(m)
    return ok(_out(m))


@router.delete("/{mid}")
async def delete(mid: str, me=Depends(get_current_user)):
    """删除 MCP 服务。"""
    async with async_session() as s:
        m = (await s.execute(select(Mcp).where(Mcp.id == mid))).scalar_one_or_none()
        if not m:
            raise BizException(ErrorCode.NOT_FOUND, "MCP 服务不存在")
        await s.delete(m)
        await s.commit()
    return ok({"success": True})


@router.post("/{mid}/test")
async def test(mid: str, me=Depends(get_current_user)):
    """测试 MCP 连接（真客户端，更新 status/tool_count）。"""
    from app.core.agent.tool_adapters.mcp_tools import test_connection
    async with async_session() as s:
        m = (await s.execute(select(Mcp).where(Mcp.id == mid))).scalar_one_or_none()
    if not m:
        raise BizException(ErrorCode.NOT_FOUND, "MCP 服务不存在")
    result = await test_connection(m)
    # 回写 status / tool_count
    async with async_session() as s:
        m2 = (await s.execute(select(Mcp).where(Mcp.id == mid))).scalar_one_or_none()
        if m2:
            m2.status = "on" if result["success"] else "err"
            m2.tool_count = result["toolCount"]
            await s.commit()
    return ok(result)

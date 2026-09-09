"""tools 路由：/tools CRUD + 测试端点。

auth.key 在落库前经 Fernet 加密，读取时解密后返回（前端负责掩码显示）。
"""
from fastapi import APIRouter, Depends
from fastapi import Body
from sqlalchemy import select

from app.api.deps import get_current_user, require_roles
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.tool import Tool
from app.schemas.tool import ToolCreate, ToolUpdate
from app.security.crypto import decrypt, encrypt

router = APIRouter(prefix="/tools", tags=["tools"])


def _encrypt_auth(auth: dict | None) -> dict | None:
    """加密 auth.key 后返回。"""
    if auth and auth.get("key") and auth.get("mode", "none") != "none":
        return {**auth, "key": encrypt(auth["key"])}
    return auth


def _decrypt_auth(auth: dict | None) -> dict | None:
    """解密 auth.key 后返回；解密失败时原样返回。"""
    if auth and auth.get("key") and auth.get("mode", "none") != "none":
        try:
            return {**auth, "key": decrypt(auth["key"])}
        except ValueError:
            pass
    return auth


def _out(t: Tool) -> dict:
    """构造工具响应字典。"""
    return {
        "id": str(t.id),
        "name": t.name,
        "type": t.type,
        "desc": t.description or "",
        "sig": t.sig or "",
        "enabled": t.enabled,
        "params": t.params or [],
        "auth": _decrypt_auth(t.auth) or {"mode": "none", "key": ""},
        "config": t.config or {},
        "createdAt": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("")
async def list_(me=Depends(get_current_user)):
    """列出所有工具。

    返回所有工具列表，按创建时间倒序排列。
    包含工具的基本信息和解密后的认证配置。
    """
    async with async_session() as s:
        rows = (await s.execute(select(Tool).order_by(Tool.created_at.desc()))).scalars().all()
    return ok([_out(t) for t in rows])


@router.post("")
async def create(body: ToolCreate, me=Depends(require_roles("admin"))):
    """创建新工具。

    创建一个新的工具配置，包含名称、类型、参数签名、认证信息等。
    认证密钥会在保存前使用 Fernet 加密存储。
    仅管理员有权限执行此操作。
    """
    t = Tool(
        name=body.name,
        type=body.type,
        description=body.desc,
        sig=body.sig,
        enabled=body.enabled,
        params=[p.model_dump() for p in body.params],
        auth=_encrypt_auth(body.auth.model_dump()) if body.auth else None,
        config=body.config or None,
    )
    async with async_session() as s:
        s.add(t)
        await s.commit()
        await s.refresh(t)
    return ok(_out(t))


@router.get("/{tid}")
async def detail(tid: str, me=Depends(get_current_user)):
    """获取工具详情。

    根据工具 ID 获取单个工具的完整信息。
    返回解密后的认证配置供前端使用。
    """
    async with async_session() as s:
        t = (await s.execute(select(Tool).where(Tool.id == tid))).scalar_one_or_none()
    if not t:
        raise BizException(ErrorCode.NOT_FOUND, "工具不存在")
    return ok(_out(t))


@router.put("/{tid}")
async def update(tid: str, body: ToolUpdate, me=Depends(require_roles("admin"))):
    """更新工具配置。

    更新指定工具的名称、类型、参数签名、认证信息等。
    认证密钥更新后会使用 Fernet 加密存储。
    仅管理员有权限执行此操作。
    """
    async with async_session() as s:
        t = (await s.execute(select(Tool).where(Tool.id == tid))).scalar_one_or_none()
        if not t:
            raise BizException(ErrorCode.NOT_FOUND, "工具不存在")
        for field, attr in [
            ("name", "name"), ("type", "type"), ("desc", "description"),
            ("sig", "sig"), ("enabled", "enabled"),
        ]:
            val = getattr(body, field)
            if val is not None:
                setattr(t, attr, val)
        if body.params is not None:
            t.params = [p.model_dump() for p in body.params]
        if body.auth is not None:
            t.auth = _encrypt_auth(body.auth.model_dump())
        if body.config is not None:
            t.config = body.config
        await s.commit()
        await s.refresh(t)
    return ok(_out(t))


@router.delete("/{tid}")
async def delete(tid: str, me=Depends(require_roles("admin"))):
    """删除工具。

    永久删除指定的工具配置。
    仅管理员有权限执行此操作。
    """
    async with async_session() as s:
        t = (await s.execute(select(Tool).where(Tool.id == tid))).scalar_one_or_none()
        if not t:
            raise BizException(ErrorCode.NOT_FOUND, "工具不存在")
        await s.delete(t)
        await s.commit()
    return ok({"success": True})


@router.post("/{tid}/test")
async def test(tid: str, body: dict = Body(default={}), me=Depends(get_current_user)):
    """测试工具执行。

    根据工具类型执行测试：HTTP 工具发送请求、内置工具调用本地函数、Python 工具在沙箱中执行。
    用于验证工具配置是否正确，返回执行结果或错误信息。
    """
    from app.services.tool_service import execute_tool
    return ok(await execute_tool(tid, body.get("args", {})))

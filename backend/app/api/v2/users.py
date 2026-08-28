"""用户管理路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func

from app.api.deps import require_roles
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, to_user_out
from app.security.password import hash_password, validate_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def list_users(limit: int = 50, offset: int = 0, me=Depends(require_roles("admin"))):
    """列出用户（admin 专属）。"""
    async with async_session() as s:
        rows = (
            await s.execute(select(User).order_by(User.created_at).limit(limit).offset(offset))
        ).scalars().all()
        total = (await s.execute(select(func.count(User.id)))).scalar()
    return ok({"items": [to_user_out(u) for u in rows], "total": total})


@router.post("")
async def create_user(body: UserCreate, me=Depends(require_roles("admin"))):
    """创建用户（admin 专属）。"""
    if body.role not in ("admin", "editor", "viewer"):
        raise BizException(ErrorCode.PARAM_ERROR, "角色必须为 admin/editor/viewer")
    validate_password(body.password)

    async with async_session() as s:
        exists = (
            await s.execute(select(User).where(User.username == body.username))
        ).scalar_one_or_none()
        if exists:
            raise BizException(ErrorCode.PARAM_ERROR, "用户名已存在")

        u = User(
            username=body.username,
            hashed_password=hash_password(body.password),
            display_name=body.display_name,
            email=body.email,
            role=body.role,
        )
        s.add(u)
        await s.commit()
        await s.refresh(u)

    return ok(to_user_out(u))


@router.patch("/{uid}")
async def update_user(uid: str, body: UserUpdate, me=Depends(require_roles("admin", "editor", "viewer"))):
    """更新用户（admin 可改全部字段；普通用户只能改自己的 display_name/password/email）。"""
    async with async_session() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if not u:
            raise BizException(ErrorCode.NOT_FOUND, "用户不存在")

        if me.role != "admin":
            if str(u.id) != str(me.id):
                raise BizException(ErrorCode.FORBIDDEN, "只能修改自己的信息")

        if body.display_name is not None:
            u.display_name = body.display_name
        if body.email is not None:
            u.email = body.email
        if body.password is not None:
            validate_password(body.password)
            u.hashed_password = hash_password(body.password)

        if me.role == "admin":
            if body.role is not None:
                if body.role not in ("admin", "editor", "viewer"):
                    raise BizException(ErrorCode.PARAM_ERROR, "角色必须为 admin/editor/viewer")
                u.role = body.role
            if body.is_active is not None:
                if str(u.id) == str(me.id) and body.is_active is False:
                    raise BizException(ErrorCode.FORBIDDEN, "不能禁用自己")
                u.is_active = body.is_active

        await s.commit()
        await s.refresh(u)

    return ok(to_user_out(u))


@router.delete("/{uid}")
async def delete_user(uid: str, me=Depends(require_roles("admin"))):
    """删除用户（admin 专属，不能删自己 / 最后一个 admin）。"""
    if uid == str(me.id):
        raise BizException(ErrorCode.FORBIDDEN, "不能删除自己")

    async with async_session() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if not u:
            raise BizException(ErrorCode.NOT_FOUND, "用户不存在")

        if u.role == "admin":
            admin_count = (
                await s.execute(
                    select(func.count(User.id)).where(User.role == "admin", User.is_active == True)  # noqa: E712
                )
            ).scalar()
            if admin_count <= 1:
                raise BizException(ErrorCode.FORBIDDEN, "不能删除最后一个管理员")

        await s.delete(u)
        await s.commit()

    return ok({"success": True})

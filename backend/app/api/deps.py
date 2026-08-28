"""请求依赖模块。

提供从 Authorization 头解析 JWT、获取当前登录用户等 FastAPI 依赖。
"""
from fastapi import Header, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.security.jwt import decode_token
from app.models.user import User
from app.exceptions import BizException, ErrorCode


def _claims_from_header(authorization: str, expect_typ: str = "access") -> dict:
    """从 Authorization 头解析 Bearer token 并返回声明（claims）。

    Args:
        authorization: 原始 Authorization 头值，需以 "Bearer " 开头。
        expect_typ: 期望的 token 类型（access/refresh），不匹配则抛 UNAUTHORIZED。

    Returns:
        解码后的 JWT claims 字典。

    Raises:
        BizException: 缺少认证信息、token 无效或类型不符时抛出。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise BizException(ErrorCode.UNAUTHORIZED, "缺少认证信息")
    claims = decode_token(authorization[7:])
    if claims.get("typ") != expect_typ:
        raise BizException(ErrorCode.UNAUTHORIZED, "token 类型错误")
    return claims


async def get_current_user(authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)) -> User:
    """从 Authorization 头解析 JWT 并返回当前用户。

    校验 Bearer access token，按 token 中的 sub(user_id) 查询用户；
    无 token / token 无效 / 用户禁用均抛 BizException(UNAUTHORIZED)。
    """
    claims = _claims_from_header(authorization, "access")
    user = (await db.execute(select(User).where(User.id == claims["sub"]))).scalar_one_or_none()
    if not user or not user.is_active:
        raise BizException(ErrorCode.UNAUTHORIZED, "用户不存在或已禁用")
    return user


def require_roles(*roles: str):
    """角色守卫依赖工厂：校验当前用户角色是否在允许列表内。

    用法：me=Depends(require_roles("admin")) 或 me=Depends(require_roles("admin", "editor"))
    """
    async def _check(me: User = Depends(get_current_user)) -> User:
        if me.role not in roles:
            raise BizException(ErrorCode.FORBIDDEN, "无权限执行此操作")
        return me
    return _check

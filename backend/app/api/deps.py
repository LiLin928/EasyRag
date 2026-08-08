from fastapi import Header, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.security.jwt import decode_token
from app.models.user import User
from app.exceptions import BizException, ErrorCode


def _claims_from_header(authorization: str, expect_typ: str = "access") -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise BizException(ErrorCode.UNAUTHORIZED, "缺少认证信息")
    claims = decode_token(authorization[7:])
    if claims.get("typ") != expect_typ:
        raise BizException(ErrorCode.UNAUTHORIZED, "token 类型错误")
    return claims


async def get_current_user(authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)) -> User:
    claims = _claims_from_header(authorization, "access")
    user = (await db.execute(select(User).where(User.id == claims["sub"]))).scalar_one_or_none()
    if not user or not user.is_active:
        raise BizException(ErrorCode.UNAUTHORIZED, "用户不存在或已禁用")
    return user

"""认证路由模块。

提供登录、刷新 token、获取当前用户信息等接口。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import _claims_from_header, get_current_user
from app.api.response import ok
from app.db.session import get_db
from app.models.user import User
from app.security.password import verify_password
from app.security.jwt import create_access_token, create_refresh_token
from app.schemas.auth import LoginParams, LoginResult, RefreshParams, RefreshResult, UserInfo
from app.exceptions import BizException, ErrorCode
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(params: LoginParams, db: AsyncSession = Depends(get_db)):
    """用户登录。

    按用户名查询用户并校验密码，成功后签发 access/refresh token；
    用户不存在或密码错误均抛 LOGIN_FAILED。
    """
    user = (await db.execute(select(User).where(User.username == params.username))).scalar_one_or_none()
    if not user or not verify_password(params.password, user.hashed_password):
        raise BizException(ErrorCode.LOGIN_FAILED, "用户名或密码错误")
    return ok(LoginResult(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.jwt_access_expire,
        user=UserInfo(id=str(user.id), username=user.username, display_name=user.display_name, role=user.role),
    ).model_dump())


@router.post("/refresh")
async def refresh(params: RefreshParams):
    """用 refresh token 换取新的 access token。

    校验 refresh token 有效性与类型后，按其 sub(user_id) 重新签发 access token。
    """
    claims = _claims_from_header("Bearer " + params.refresh_token, expect_typ="refresh")
    return ok(RefreshResult(access_token=create_access_token(claims["sub"]), expires_in=settings.jwt_access_expire).model_dump())


@router.get("/user-info")
async def user_info(me: User = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return ok(UserInfo(id=str(me.id), username=me.username, display_name=me.display_name, role=me.role).model_dump())

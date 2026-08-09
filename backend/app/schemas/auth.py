"""认证相关 schema 模块。

定义登录、刷新、用户信息等请求/响应数据模型。
"""
from pydantic import BaseModel


class LoginParams(BaseModel):
    """登录请求参数。

    Attributes:
        username: 用户名。
        password: 明文密码。
    """

    username: str
    password: str


class UserInfo(BaseModel):
    """用户信息（用于响应）。

    Attributes:
        id: 用户 id（字符串形式 UUID）。
        username: 用户名。
        display_name: 显示名，可空。
        role: 角色。
    """

    id: str
    username: str
    display_name: str | None = None
    role: str


class LoginResult(BaseModel):
    """登录成功响应载荷。

    Attributes:
        access_token: 访问令牌。
        refresh_token: 刷新令牌。
        expires_in: access token 有效期（秒）。
        user: 用户信息。
    """

    access_token: str
    refresh_token: str
    expires_in: int
    user: UserInfo


class RefreshParams(BaseModel):
    """刷新 token 请求参数。

    Attributes:
        refresh_token: 刷新令牌。
    """

    refresh_token: str


class RefreshResult(BaseModel):
    """刷新 token 响应载荷。

    Attributes:
        access_token: 新签发的访问令牌。
        expires_in: access token 有效期（秒）。
    """

    access_token: str
    expires_in: int

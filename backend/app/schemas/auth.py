from pydantic import BaseModel


class LoginParams(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    role: str


class LoginResult(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserInfo


class RefreshParams(BaseModel):
    refresh_token: str


class RefreshResult(BaseModel):
    access_token: str
    expires_in: int

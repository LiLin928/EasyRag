"""用户管理 Schema。"""
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    email: str | None = None
    role: str = "viewer"


class UserUpdate(BaseModel):
    display_name: str | None = None
    password: str | None = None
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    email: str | None = None
    role: str
    is_active: bool
    created_at: str


def to_user_out(u) -> dict:
    return {
        "id": str(u.id),
        "username": u.username,
        "display_name": u.display_name,
        "email": u.email,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else "",
    }

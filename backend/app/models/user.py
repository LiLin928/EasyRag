"""用户 ORM 模型模块。"""
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPk


class User(Base, UUIDPk, TimestampMixin):
    """用户表模型。

    Attributes:
        username: 用户名，唯一且有索引。
        email: 邮箱，可空，唯一。
        hashed_password: 密码哈希值。
        display_name: 显示名，可空。
        role: 角色名，默认 "admin"。
        is_active: 是否启用，默认 True。
    """

    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

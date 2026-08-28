"""工具 ORM 模型。

tools 表存储 HTTP / 内置 / Python 工具定义，供 Agent / Skill / Workflow 挂载调用。
auth.key 在落库前经 Fernet 加密。
"""
from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class Tool(Base, UUIDPk, TimestampMixin):
    """工具表，存储 HTTP / 内置 / Python 工具定义。"""

    __tablename__ = "tools"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="HTTP")  # HTTP / 内置 / Python
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sig: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 函数签名
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    params: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    auth: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # {mode, key}

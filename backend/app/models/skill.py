"""技能 ORM 模型。

skills 表存储技能定义（触发器 + prompt + 挂载的资源），可 builtin / custom。
"""
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class Skill(Base, UUIDPk, TimestampMixin):
    """技能表，存储技能定义（触发器 + prompt + 挂载资源）。"""

    __tablename__ = "skills"
    icon: Mapped[str] = mapped_column(String(32), default="🔧")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), default="custom")  # builtin / custom
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tools: Mapped[Optional[list]] = mapped_column(JSONB, default=list)  # tool id 列表
    docs: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    wfs: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    examples: Mapped[Optional[list]] = mapped_column(JSONB, default=list)  # [{q, a}]
    scripts: Mapped[Optional[list]] = mapped_column(JSONB, default=list)  # [{name, content}]
    budget: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Token 预算
    used: Mapped[int] = mapped_column(Integer, default=0)  # 已用 Token

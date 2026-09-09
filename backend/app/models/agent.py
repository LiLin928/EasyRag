"""智能体 ORM 模型。

agents 表存储智能体配置（模型 + prompt + 挂载的工具/文档/工作流/MCP/技能）。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class Agent(Base, UUIDPk, TimestampMixin):
    """智能体表，存储智能体配置（模型 + prompt + 挂载资源）。"""

    __tablename__ = "agents"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(128), default="gpt-4o")
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    temp: Mapped[float] = mapped_column(Float, default=0.7)  # 温度
    maxtok: Mapped[str] = mapped_column(String(16), default="2048")  # 最大 Token 数
    tools: Mapped[Optional[list]] = mapped_column(JSONB, default=list)  # tool id 列表
    docs: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    wfs: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    mcps: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    skills: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_active: Mapped[Optional[datetime]] = mapped_column(nullable=True)

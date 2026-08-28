"""MCP (Model Context Protocol) ORM 模型。

mcps 表存储 MCP 服务连接配置，支持 stdio / SSE 两种类型。
env 中的敏感值在落库前经 Fernet 加密。
"""
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class Mcp(Base, UUIDPk, TimestampMixin):
    """MCP 服务表，存储 stdio / SSE 连接配置。"""

    __tablename__ = "mcps"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    tp: Mapped[str] = mapped_column(String(16), default="stdio")  # stdio / SSE
    cmd: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # stdio 命令 / SSE url
    status: Mapped[str] = mapped_column(String(16), default="off")  # on / off / err
    tool_count: Mapped[int] = mapped_column(Integer, default=0)
    env: Mapped[Optional[list]] = mapped_column(JSONB, default=list)  # [{k, v}]
    timeout: Mapped[int] = mapped_column(Integer, default=30)  # 超时秒数

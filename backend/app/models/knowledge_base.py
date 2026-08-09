"""知识库 ORM 模型。"""
import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class KnowledgeBase(Base, UUIDPk, TimestampMixin):
    """知识库表，用户文档的容器，绑定检索场景与分块参数。

    Attributes:
        user_id: 所属用户（FK users.id，级联删除）。
        name: 知识库名称。
        description: 描述（可空）。
        scene: 绑定的检索场景编码（默认 general）。
        cover: 封面色值/标识（可空）。
        chunk_size: 分块大小（字符），默认 512。
        chunk_overlap: 分块重叠，默认 64。
        retrieval_top_k: 检索返回条数，默认 5。
        doc_count: 文档数（维护字段）。
        total_size: 文档总字节数（维护字段）。
    """

    __tablename__ = "knowledge_bases"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene: Mapped[str] = mapped_column(String(32), default="general")
    cover: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chunk_size: Mapped[int] = mapped_column(Integer, default=512)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=64)
    retrieval_top_k: Mapped[int] = mapped_column(Integer, default=5)
    doc_count: Mapped[int] = mapped_column(Integer, default=0)
    total_size: Mapped[int] = mapped_column(BigInteger, default=0)

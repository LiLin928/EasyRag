"""分块 ORM 模型（含向量列与全文检索列）。"""
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin, UUIDPk

EMBEDDING_DIM = 1024   # 与 config.embedding_dim 对齐；改维度需重建本表


class Chunk(Base, UUIDPk, TimestampMixin):
    """分块表，文档结构化分块 + 向量 + 全文检索。

    Attributes:
        document_id: 所属文档（FK documents.id，级联删除）。
        kb_id: 知识库 id（字符串索引，检索按 kb 过滤）。
        clause_title: 所属条款/标题（可空）。
        section_path: 章节路径（A > B > C）。
        content: 分块正文。
        content_search: 全文检索用副本（pg_trgm 索引）。
        page_number: 页码。
        element_count: 元素数。
        seq: 块序号。
        embedding: 向量（vector(1024)，向量化后填）。
        embedding_model: 生成向量的模型名。
    """

    __tablename__ = "chunks"
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    kb_id: Mapped[str] = mapped_column(String(36), index=True)
    clause_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    content_search: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    element_count: Mapped[int] = mapped_column(Integer, default=0)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)

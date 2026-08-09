"""文档结构树与元素定位 ORM 模型。"""
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin, UUIDPk

EMBEDDING_DIM = 1024


class TreeNode(Base, UUIDPk, TimestampMixin):
    """文档结构树节点表。

    Attributes:
        document_id: 所属文档（FK documents.id，级联删除）。
        parent_id: 父节点（FK doc_tree_nodes.id，级联删除；根节点为 None）。
        level: 层级（0=根）。
        sort_order: 同级排序。
        title: 节点标题（章节名）。
        summary: 摘要（暂为 title，LLM 摘要后续）。
        element_count: 节点下元素数。
        page_start/page_end: 起止页码。
        nav_embedding: 导航向量（用于"导航到章节"语义匹配）。
    """

    __tablename__ = "doc_tree_nodes"
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("doc_tree_nodes.id", ondelete="CASCADE"), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    element_count: Mapped[int] = mapped_column(Integer, default=0)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nav_embedding: Mapped[Optional[list]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


class ElementPosition(Base, UUIDPk, TimestampMixin):
    """文档元素定位表（原文元素：文本/表格/图片/标题）。

    Attributes:
        document_id: 所属文档（FK documents.id，级联删除）。
        chunk_id: 关联分块（FK chunks.id，删除置空）。
        tree_node_id: 所属树节点（FK doc_tree_nodes.id，删除置空）。
        element_type: 元素类型 text/table/image/heading。
        element_index: 文档内顺序索引。
        page_number: 页码。
        content: 文本/表格 HTML/标题。
        image_key: 图片存储键。
        ocr_text: OCR 文本（图片用）。
        metadata_: 元数据 JSONB（列名 "metadata"，避开 Base.metadata）。
    """

    __tablename__ = "element_positions"
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True, index=True)
    tree_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("doc_tree_nodes.id", ondelete="SET NULL"), nullable=True, index=True)
    element_type: Mapped[str] = mapped_column(String(20))
    element_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

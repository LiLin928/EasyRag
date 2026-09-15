"""子分段模型（父子分段模式下的检索单元）。

子分段是父子分段模式下的细粒度检索单元。
每个子分段关联到一个树节点（父分段），通过 tree_node_id 进行关联。

检索时：
1. 向量检索命中子分段
2. 通过 tree_node_id 映射回父分段（TreeNode）
3. 返回父分段的完整内容
"""
import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin, UUIDPk

EMBEDDING_DIM = 1024  # 与 chunks 表保持一致


class ChildChunk(Base, UUIDPk, TimestampMixin):
    """子分段表。

    父子分段模式下的细粒度检索单元。
    通过 tree_node_id 关联到父分段（TreeNode）。

    Attributes:
        document_id: 所属文档。
        tree_node_id: 关联的树节点（父分段）。
        kb_id: 知识库 ID。
        position: 在父分段内的位置（从 1 开始）。
        content: 子分段文本内容。
        content_search: 全文检索用副本。
        char_count: 字符数。
        embedding: 向量（只对子分段建索引）。
        embedding_model: 向量模型名。
        metadata: 元数据（包含父分段信息）。
        enabled: 是否启用。
    """

    __tablename__ = "child_chunks"
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    tree_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc_tree_nodes.id", ondelete="CASCADE"), index=True
    )
    kb_id: Mapped[str] = mapped_column(String(36), index=True)
    position: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text)
    content_search: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
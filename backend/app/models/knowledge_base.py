"""知识库 ORM 模型。"""
import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

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
        retrieval_mode: 检索模式 traditional(传统单层) / parent_child(父子分段)，默认 traditional。
        child_chunk_size: 父子分段模式下子分段目标大小（字符），默认 200。
        child_chunk_overlap: 父子分段模式下子分段重叠字符数，默认 50。
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
    # 父子分段相关配置（方案§9：知识库级别配置）
    retrieval_mode: Mapped[str] = mapped_column(
        String(20),
        default="traditional",
        comment="检索模式：traditional(传统单层) / parent_child(父子分段)",
    )
    child_chunk_size: Mapped[int] = mapped_column(
        Integer,
        default=200,
        comment="父子分段模式下子分段目标大小（字符数）",
    )
    child_chunk_overlap: Mapped[int] = mapped_column(
        Integer,
        default=50,
        comment="父子分段模式下子分段重叠字符数",
    )
    embedding_model_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True
    )
    rerank_model_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True
    )
    retrieval_config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

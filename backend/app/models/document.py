"""文档与解析任务 ORM 模型。"""
import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class Document(Base, UUIDPk, TimestampMixin):
    """文档表，记录上传文件元信息与解析状态。

    Attributes:
        kb_id: 所属知识库（FK knowledge_bases.id，级联删除）。
        user_id: 上传用户（FK users.id）。
        name: 原始文件名。
        ext: 扩展名（pdf/docx/xlsx/md/txt...）。
        size: 文件字节数。
        pages: 页数（PDF）。
        mode: 解析模式 fast/precision。
        status: 解析状态 pending/parsing/done/failed。
        pct: 解析进度百分比。
        error: 失败原因。
        file_key: 存储键（Storage 抽象用）。
        element_count: 元素数（解析后填）。
        chunk_count: 分块数（解析后填）。
    """

    __tablename__ = "documents"
    kb_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    ext: Mapped[str] = mapped_column(String(16))
    size: Mapped[int] = mapped_column(BigInteger)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[str] = mapped_column(String(16), default="fast")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    pct: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_key: Mapped[str] = mapped_column(String(512))
    element_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)


class ParseTask(Base, UUIDPk, TimestampMixin):
    """解析任务表，供前端轮询解析进度。

    Attributes:
        doc_id: 关联文档（FK documents.id，级联删除）。
        kb_id: 知识库 id（字符串，便于 worker 检索）。
        status: 任务状态 pending/parsing/done/failed。
        pct: 进度百分比。
        error: 失败原因。
    """

    __tablename__ = "parse_tasks"
    doc_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    kb_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    pct: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

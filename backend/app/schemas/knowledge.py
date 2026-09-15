"""knowledge 相关 Pydantic 请求/响应模型。"""
from typing import Literal

from pydantic import BaseModel, Field


class KBCreate(BaseModel):
    """知识库创建请求体。"""

    name: str
    desc: str | None = None
    scene: str = "general"
    cover: str | None = None
    # 父子分段配置（方案§9）：不传则使用模型默认值
    retrieval_mode: Literal["traditional", "parent_child"] | None = None
    child_chunk_size: int | None = Field(default=None, ge=50, le=2000)
    child_chunk_overlap: int | None = Field(default=None, ge=0, le=500)


class KBUpdate(BaseModel):
    """知识库更新请求体（部分更新）。"""

    name: str | None = None
    desc: str | None = None
    scene: str | None = None
    cover: str | None = None
    # 父子分段配置（方案§9）：None 表示不修改
    retrieval_mode: Literal["traditional", "parent_child"] | None = None
    child_chunk_size: int | None = Field(default=None, ge=50, le=2000)
    child_chunk_overlap: int | None = Field(default=None, ge=0, le=500)


class KBOut(BaseModel):
    """知识库响应体。"""

    id: str
    name: str
    description: str | None = None
    scene: str
    cover: str | None = None
    doc_count: int = 0
    total_size: int = 0
    chunk_count: int = 0
    last_test_at: str | None = None
    created_at: str
    # 父子分段配置（方案§9）
    retrieval_mode: str = "traditional"
    child_chunk_size: int = 200
    child_chunk_overlap: int = 50
    # camelCase aliases for legacy frontend
    desc: str = ""
    docCount: int = 0
    totalSize: str = ""
    createdAt: str = ""


class MetadataFieldCreate(BaseModel):
    """Metadata field creation request."""

    key: str
    name: str
    scope: Literal["document", "chunk"]
    data_type: Literal["string", "number", "date", "select", "boolean"]
    options: list[str] = []
    default_value: object | None = None
    required: bool = False
    filterable: bool = False
    retrieval_filterable: bool = False
    visible: bool = True
    sort_order: int = 0


class MetadataFieldUpdate(BaseModel):
    """Metadata field partial update request."""

    name: str | None = None
    options: list[str] | None = None
    default_value: object | None = None
    required: bool | None = None
    filterable: bool | None = None
    retrieval_filterable: bool | None = None
    visible: bool | None = None
    sort_order: int | None = None


class MetadataFieldReorder(BaseModel):
    """Metadata field sort-order request."""

    ids: list[str]


class MetadataFieldOut(BaseModel):
    """Metadata field response."""

    id: str
    kb_id: str
    key: str
    name: str
    scope: str
    data_type: str
    options: list = []
    default_value: object | None = None
    required: bool = False
    filterable: bool = False
    retrieval_filterable: bool = False
    visible: bool = True
    built_in: bool = False
    mapped_field: str | None = None
    sort_order: int = 0


class RetrievalSettingsUpdate(BaseModel):
    """Retrieval settings partial update request."""

    embedding_model_id: str | None = None
    rerank_model_id: str | None = None
    retrieval_config: dict | None = None


class RetrievalSettingsOut(BaseModel):
    """Effective retrieval settings response."""

    values: dict
    resolved: dict
    embedding_model: dict | None
    rerank_model: dict | None
    rebuild_required: bool


class ReembedRequest(BaseModel):
    """Chunk reindex request scoped to one owned knowledge base."""

    kb_id: str
    document_ids: list[str] = []
    chunk_ids: list[str] = []

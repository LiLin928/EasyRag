"""knowledge 相关 Pydantic 请求/响应模型。"""
from pydantic import BaseModel


class KBCreate(BaseModel):
    """知识库创建请求体。"""

    name: str
    description: str | None = None
    scene: str = "general"
    cover: str | None = None


class KBUpdate(BaseModel):
    """知识库更新请求体（部分更新）。"""

    name: str | None = None
    description: str | None = None
    scene: str | None = None
    cover: str | None = None


class KBOut(BaseModel):
    """知识库响应体。"""

    id: str
    name: str
    description: str | None = None
    scene: str
    cover: str | None = None
    doc_count: int = 0
    total_size: int = 0
    created_at: str

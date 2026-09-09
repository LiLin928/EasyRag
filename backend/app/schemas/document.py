"""document 相关 Pydantic 响应模型。"""
from pydantic import BaseModel


class DocOut(BaseModel):
    """文档响应体。"""

    id: str
    kb_id: str
    name: str
    ext: str
    size: int
    status: str
    pct: int = 0
    mode: str = "fast"
    pages: int = 0
    element_count: int = 0
    created_at: str = ""

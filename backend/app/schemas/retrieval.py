"""检索相关 Schema 定义。"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class RetrievalRequest(BaseModel):
    """检索请求。"""
    query: str = Field(..., description="查询文本")
    kb_id: str = Field(..., description="知识库ID")
    top_k: int = Field(default=5, description="返回数量")
    method: str = Field(default="hybrid", description="检索方法：vector/keyword/hybrid")
    vector_top_k: int = Field(default=20, description="向量检索返回数量")
    keyword_top_k: int = Field(default=20, description="关键词检索返回数量")
    similarity_threshold: float = Field(default=0.3, description="相似度阈值")
    rerank_enabled: bool = Field(default=True, description="是否启用重排序")
    rerank_top_n: int = Field(default=10, description="重排序返回数量")
    navigation_enabled: bool = Field(default=True, description="是否启用导航式检索")
    metadata_filters: Dict[str, Any] = Field(default={}, description="元数据过滤条件")


class RetrievalCandidate(BaseModel):
    """检索候选项。"""
    rank: int = Field(..., description="排名")
    chunk_id: str = Field(..., description="分块ID")
    document_id: str = Field(..., description="文档ID")
    document_name: str = Field(..., description="文档名称")
    content: str = Field(..., description="内容")
    page_number: int = Field(..., description="页码")
    vector_score: float = Field(default=0.0, description="向量检索分数")
    keyword_score: float = Field(default=0.0, description="关键词检索分数")
    final_score: float = Field(default=0.0, description="最终分数")
    metadata: Dict[str, Any] = Field(default={}, description="元数据")


class RetrievalResult(BaseModel):
    """检索结果。"""
    query: str = Field(..., description="查询文本")
    candidates: List[RetrievalCandidate] = Field(default=[], description="候选项列表")
    total: int = Field(default=0, description="总数")
    retrieval_time_ms: int = Field(default=0, description="检索耗时(ms)")
"""HybridRetriever：把检索管线包装为 LangChain BaseRetriever，供 chat/agent/workflow 复用。"""
from typing import List

from langchain_core.callbacks import AsyncCallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import PrivateAttr

from app.core.retrieval.pipeline import RetrievalPipeline, RetrievalResult


class HybridRetriever(BaseRetriever):
    """混合检索 Retriever（向量+全文+RRF+Rerank+导航），适配 LangChain Runnable 接口。"""

    doc_ids: List[str]
    scene_config: object
    top_k: int = 5
    enable_nav: bool = True
    _pipeline: RetrievalPipeline = PrivateAttr()
    _last_result: RetrievalResult | None = PrivateAttr(default=None)

    def __init__(self, **data):
        super().__init__(**data)
        self._pipeline = RetrievalPipeline(scene_config=self.scene_config)

    @property
    def last_result(self):
        """最近一次检索的完整结果（含 references/nav_info）。"""
        return self._pipeline.last_result

    def _get_relevant_documents(self, query, *, run_manager):  # 同步未实现，使用 ainvoke
        raise NotImplementedError("use ainvoke")

    async def _aget_relevant_documents(self, query: str, *,
                                       run_manager: AsyncCallbackManagerForRetrieverRun) -> List[Document]:
        result = await self._pipeline.search(query, self.doc_ids, self.top_k, self.enable_nav)
        self._last_result = result
        return [Document(page_content=c.get("content", ""), metadata={
            "chunk_id": str(c.get("id")), "doc_id": str(c.get("document_id")),
            "node_title": c.get("clause_title"), "page_number": c.get("page_number", 1),
            "section_path": c.get("section_path"),
            "score": c.get("rerank_score", c.get("rrf", 0)),
        }) for c in result.chunks]

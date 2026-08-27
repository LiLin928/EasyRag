"""/navigate /search 检索调试 API。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.api.response import ok
from app.core.retrieval import fulltext_search, navigator, reranker, rrf_merge, vector_search
from app.core.scenes import get_scene_config
from app.providers.langchain_factory import build_embeddings

router = APIRouter(tags=["retrieval"])


class NavReq(BaseModel):
    """导航请求。"""

    question: str
    document_ids: list[str]
    top_n: int = 3


@router.post("/navigate")
async def navigate_api(req: NavReq, me=Depends(get_current_user)):
    """结构导航：返回最相关章节锚点及是否回退。"""
    emb = await build_embeddings()
    q_emb = await emb.aembed_query(req.question)
    cfg = await get_scene_config("general")
    r = await navigator.navigate(q_emb, req.document_ids, req.top_n, cfg.nav_confidence_threshold)
    return ok({"anchors": r["anchors"], "fallback_used": not r["scoped"]})


class SearchReq(BaseModel):
    """检索请求。"""

    question: str
    document_ids: list[str]
    top_k: int = 5
    enable_rerank: bool = True


@router.post("/search")
async def search_api(req: SearchReq, me=Depends(get_current_user)):
    """混合检索调试：向量+全文+RRF（含是否触发 rerank 判定）。"""
    emb = await build_embeddings()
    q_emb = await emb.aembed_query(req.question)
    v = await vector_search.search(q_emb, [], req.document_ids, None, 20)
    k = await fulltext_search.search(req.question, [], req.document_ids, None, 20)
    fused = rrf_merge.merge(v, k)
    triggered = False
    if req.enable_rerank and reranker.should_rerank(fused, 0.02):
        triggered = True
    return ok({"results": fused[:req.top_k], "rerank_triggered": triggered})

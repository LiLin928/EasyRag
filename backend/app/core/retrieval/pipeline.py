"""检索管线编排：向量 + 全文 → RRF → 条件 Rerank → 可选导航缩域。"""
from dataclasses import dataclass, field

from app.core.retrieval import fulltext_search, navigator, reranker, rrf_merge, vector_search
from app.core.reference_builder import build_references
from app.providers.langchain_factory import build_embeddings, build_reranker_from_config


@dataclass
class RetrievalResult:
    """检索结果。"""

    chunks: list[dict] = field(default_factory=list)
    references: list[dict] = field(default_factory=list)
    nav_info: dict | None = None
    mode: str = "hybrid"
    rerank_triggered: bool = False


class RetrievalPipeline:
    """统一检索编排，参数来自场景配置（get_scene_config）。"""

    def __init__(self, scene_config):
        self.cfg = scene_config
        self.last_result: RetrievalResult | None = None

    async def _embed_query(self, query: str) -> list[float]:
        """查询向量化。"""
        emb = await build_embeddings()
        return await emb.aembed_query(query)

    async def _reranker(self):
        """按 settings 配置构造 ApiReranker（未配则返回 None）。"""
        from app.services.settings_service import get_default_model
        cfg = await get_default_model("rerank", "rerank") or await get_default_model("rerank")
        if not cfg:
            return None
        return await build_reranker_from_config(cfg)

    async def search(self, query: str, doc_ids: list[str], top_k: int = 5, enable_nav: bool = True) -> RetrievalResult:
        """执行检索：embed → (导航缩域) → 向量+全文 → RRF → (条件 rerank) → 引用。"""
        cfg = self.cfg
        q_emb = await self._embed_query(query)

        scope = None
        nav_info = None
        if enable_nav and cfg.navigation_enabled:
            nav_info = await navigator.navigate(q_emb, doc_ids, top_k=5, threshold=cfg.nav_confidence_threshold)
            if nav_info["scoped"]:
                scope = nav_info["scope_chunk_ids"]

        vec_hits = await vector_search.search(q_emb, kb_ids=[], doc_ids=doc_ids, scope=scope, top_k=cfg.vector_top_k)
        kw_hits = await fulltext_search.search(query, kb_ids=[], doc_ids=doc_ids, scope=scope, top_k=cfg.trgm_top_k)
        fused = rrf_merge.merge(vec_hits, kw_hits, cfg.vector_weight, cfg.keyword_weight, cfg.rrf_k)

        triggered = reranker.should_rerank(fused, cfg.rerank_threshold) and cfg.rerank_enabled
        if triggered:
            rk = await self._reranker()
            if rk:
                fused = await reranker.rerank(query, fused, cfg.rerank_top_n, rk)

        top = fused[:top_k]
        refs = build_references(top)
        result = RetrievalResult(chunks=top, references=refs, nav_info=nav_info,
                                 mode="nav" if scope else "hybrid", rerank_triggered=triggered)
        self.last_result = result
        return result

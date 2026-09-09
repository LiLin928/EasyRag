"""Retrieval orchestration for vector, keyword, and hybrid modes."""
from dataclasses import dataclass, field

from sqlalchemy import text

from app.core.reference_builder import build_references
from app.core.retrieval import fulltext_search, navigator, reranker, rrf_merge, vector_search
from app.core.retrieval.metadata_filter import MetadataFilter
from app.db.session import async_session
from app.providers.langchain_factory import (
    build_embeddings,
    build_embeddings_from_config,
    build_reranker_from_config,
    get_model_by_id,
)
from app.services.retrieval_settings_service import resolved_values


@dataclass
class RetrievalResult:
    chunks: list[dict] = field(default_factory=list)
    references: list[dict] = field(default_factory=list)
    nav_info: dict | None = None
    mode: str = "hybrid"
    rerank_triggered: bool = False
    rerank_skipped_reason: str | None = None


class RetrievalPipeline:
    """Coordinate retrieval channels using one effective settings snapshot."""

    def __init__(self, *, settings: dict, embedding_model=None, rerank_model=None):
        self.settings = resolved_values(settings)
        self.embedding_model = embedding_model
        self.rerank_model = rerank_model
        self.last_result: RetrievalResult | None = None

    @staticmethod
    def _model_id(model) -> str | None:
        if model is None:
            return None
        if isinstance(model, dict):
            return model.get("id")
        return str(model.id)

    @classmethod
    def _model_name(cls, model) -> str | None:
        if model is None:
            return None
        if isinstance(model, dict):
            return model.get("name")
        return model.name

    async def _embed_query(self, query: str) -> list[float]:
        model_id = self._model_id(self.embedding_model)
        if model_id is None:
            embeddings = await build_embeddings()
        else:
            model = await get_model_by_id(model_id, "embed")
            embeddings = await build_embeddings_from_config(model)
        return await embeddings.aembed_query(query)

    async def build_reranker(self):
        model_id = self._model_id(self.rerank_model)
        if model_id is None:
            return None
        model = await get_model_by_id(model_id, "rerank")
        return await build_reranker_from_config(model)

    @staticmethod
    def _single_channel(hits: list[dict], channel: str) -> list[dict]:
        score_key = f"{channel}_score"
        rank_key = "vector_rank" if channel == "vector" else "fulltext_rank"
        unused_key = "keyword_score" if channel == "vector" else "vector_score"
        result = []
        for rank, hit in enumerate(hits):
            item = {
                **hit,
                "rrf": float(hit[score_key]),
                rank_key: rank + 1,
                unused_key: None,
            }
            result.append(item)
        return result

    async def _count_recall(self, chunks: list[dict]) -> None:
        if not chunks:
            return
        chunk_ids = list(dict.fromkeys(str(chunk["id"]) for chunk in chunks))
        document_ids = list(
            dict.fromkeys(str(chunk["document_id"]) for chunk in chunks)
        )
        statement = text(
            """
            WITH recalled_chunks AS (
                UPDATE chunks
                SET recall_count = recall_count + 1
                WHERE id = ANY(cast(:chunk_ids as uuid[]))
                RETURNING id
            ), recalled_documents AS (
                UPDATE documents
                SET recall_count = recall_count + 1
                WHERE id = ANY(cast(:document_ids as uuid[]))
                RETURNING id
            )
            SELECT (SELECT count(*) FROM recalled_chunks) AS chunk_count,
                   (SELECT count(*) FROM recalled_documents) AS document_count
            """
        )
        async with async_session() as session:
            await session.execute(statement, {
                "chunk_ids": chunk_ids,
                "document_ids": document_ids,
            })
            await session.commit()

    async def search(
        self,
        query: str,
        *,
        kb_ids: list[str] | None = None,
        doc_ids: list[str] | None = None,
        scope: list[str] | None = None,
        metadata_filter: MetadataFilter | None = None,
        top_k: int | None = None,
        enable_nav: bool | None = None,
        count_recall: bool = True,
    ) -> RetrievalResult:
        cfg = self.settings
        kb_ids = kb_ids or []
        final_top_k = top_k if top_k is not None else cfg["final_top_k"]
        method = cfg["method"]

        navigation_allowed = cfg["navigation_enabled"] if enable_nav is None else enable_nav
        navigation_active = bool(navigation_allowed and doc_ids)
        q_emb = None
        if method in ("vector", "hybrid") or navigation_active:
            q_emb = await self._embed_query(query)

        nav_info = None
        resolved_scope = scope
        if navigation_active:
            nav_info = await navigator.navigate(
                q_emb,
                doc_ids,
                top_k=cfg["nav_anchor_count"],
                threshold=cfg["nav_confidence_threshold"],
            )
            if nav_info["scoped"]:
                resolved_scope = nav_info["scope_chunk_ids"]

        vector_hits: list[dict] = []
        keyword_hits: list[dict] = []
        if method in ("vector", "hybrid"):
            vector_hits = await vector_search.search(
                q_emb,
                kb_ids=kb_ids,
                doc_ids=doc_ids,
                scope=resolved_scope,
                top_k=cfg["vector_top_k"],
                metadata_filter=metadata_filter,
                embedding_model=self._model_name(self.embedding_model),
                similarity_threshold=cfg["similarity_threshold"],
            )
            vector_hits = [
                hit for hit in vector_hits
                if float(hit["vector_score"]) >= cfg["similarity_threshold"]
            ]
        if method in ("keyword", "hybrid"):
            keyword_hits = await fulltext_search.search(
                query,
                kb_ids=kb_ids,
                doc_ids=doc_ids,
                scope=resolved_scope,
                top_k=cfg["keyword_top_k"],
                metadata_filter=metadata_filter,
            )

        if method == "vector":
            fused = self._single_channel(vector_hits, "vector")
        elif method == "keyword":
            fused = self._single_channel(keyword_hits, "keyword")
        else:
            fused = rrf_merge.merge(
                vector_hits,
                keyword_hits,
                cfg["vector_weight"],
                cfg["keyword_weight"],
                cfg["rrf_k"],
            )

        rerank_triggered = False
        rerank_skipped_reason = None
        if (
            cfg["rerank_enabled"]
            and reranker.should_rerank(fused, cfg["rerank_trigger_threshold"])
        ):
            if self.rerank_model is None:
                rerank_skipped_reason = "rerank_model_not_bound"
            else:
                rerank_instance = await self.build_reranker()
                fused = await reranker.rerank(
                    query, fused, cfg["rerank_top_n"], rerank_instance
                )
                rerank_triggered = True

        top = fused[:final_top_k]
        if count_recall:
            await self._count_recall(top)

        result = RetrievalResult(
            chunks=top,
            references=build_references(top),
            nav_info=nav_info,
            mode="nav" if resolved_scope is not None and resolved_scope is not scope else method,
            rerank_triggered=rerank_triggered,
            rerank_skipped_reason=rerank_skipped_reason,
        )
        self.last_result = result
        return result

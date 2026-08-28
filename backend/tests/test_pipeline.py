"""Retrieval pipeline orchestration tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.retrieval.pipeline import RetrievalPipeline


def _settings(**overrides):
    values = {
        "method": "hybrid",
        "final_top_k": 5,
        "vector_top_k": 20,
        "keyword_top_k": 20,
        "similarity_threshold": 0.0,
        "vector_weight": 0.7,
        "keyword_weight": 0.3,
        "rrf_k": 60,
        "rerank_enabled": True,
        "rerank_top_n": 10,
        "rerank_trigger_threshold": 0.02,
        "navigation_enabled": True,
        "nav_anchor_count": 3,
        "nav_confidence_threshold": 0.15,
    }
    values.update(overrides)
    return {"values": {key: {"value": value, "source": "test"} for key, value in values.items()}}


@pytest.mark.asyncio
async def test_keyword_mode_skips_embedding_and_vector(monkeypatch):
    filters = object()
    pipeline = RetrievalPipeline(settings=_settings(method="keyword", navigation_enabled=False))
    embed = AsyncMock()
    monkeypatch.setattr(pipeline, "_embed_query", embed)

    with patch(
        "app.core.retrieval.pipeline.vector_search.search", AsyncMock()
    ) as vector, patch(
        "app.core.retrieval.pipeline.fulltext_search.search",
        AsyncMock(return_value=[{"id": "k1", "content": "K", "keyword_score": 0.9}]),
    ) as keyword:
        result = await pipeline.search(
            "q",
            kb_ids=["kb1"],
            doc_ids=["doc1"],
            metadata_filter=filters,
            count_recall=False,
        )

    embed.assert_not_called()
    vector.assert_not_called()
    assert keyword.await_args.args == ("q",)
    assert keyword.await_args.kwargs == {
        "kb_ids": ["kb1"],
        "doc_ids": ["doc1"],
        "scope": None,
        "top_k": 20,
        "metadata_filter": filters,
    }
    assert result.mode == "keyword"
    assert result.chunks[0]["rrf"] == 0.9
    assert result.chunks[0]["fulltext_rank"] == 1
    assert result.chunks[0]["vector_score"] is None


@pytest.mark.asyncio
async def test_vector_mode_applies_threshold_before_fusion(monkeypatch):
    pipeline = RetrievalPipeline(
        settings=_settings(method="vector", similarity_threshold=0.7, navigation_enabled=False)
    )
    monkeypatch.setattr(
        pipeline,
        "_embed_query",
        AsyncMock(return_value=[0.1] * 8),
    )
    hits = [
        {"id": "low", "content": "Low", "vector_score": 0.4},
        {"id": "high", "content": "High", "vector_score": 0.8},
    ]

    with patch(
        "app.core.retrieval.pipeline.vector_search.search", AsyncMock(return_value=hits)
    ), patch("app.core.retrieval.pipeline.fulltext_search.search", AsyncMock()) as keyword:
        result = await pipeline.search("q", count_recall=False)

    keyword.assert_not_called()
    assert [chunk["id"] for chunk in result.chunks] == ["high"]
    assert result.chunks[0]["rrf"] == 0.8
    assert result.chunks[0]["vector_rank"] == 1
    assert result.chunks[0]["keyword_score"] is None


@pytest.mark.asyncio
async def test_hybrid_mode_fuses_both_channels_and_counts_recall(monkeypatch):
    pipeline = RetrievalPipeline(settings=_settings(navigation_enabled=False))
    monkeypatch.setattr(
        pipeline, "_embed_query", AsyncMock(return_value=[0.1] * 8)
    )
    vector = [
        {"id": "shared", "document_id": "doc", "content": "shared", "vector_score": 0.9},
        {"id": "vector-only", "document_id": "doc", "content": "vector", "vector_score": 0.8},
    ]
    keyword = [
        {"id": "shared", "document_id": "doc", "content": "shared", "keyword_score": 0.9},
        {"id": "keyword-only", "document_id": "doc", "content": "keyword", "keyword_score": 0.8},
    ]

    class SessionContext:
        def __init__(self):
            self.execute = AsyncMock(return_value=AsyncMock())
            self.commit = AsyncMock()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    session = SessionContext()

    with patch(
        "app.core.retrieval.pipeline.vector_search.search", AsyncMock(return_value=vector)
    ), patch(
        "app.core.retrieval.pipeline.fulltext_search.search", AsyncMock(return_value=keyword)
    ), patch("app.core.retrieval.pipeline.async_session", MagicMock(return_value=session)):
        result = await pipeline.search("q", doc_ids=["d1"], top_k=2)

    assert result.mode == "hybrid"
    assert len(result.chunks) == 2
    assert result.chunks[0]["rrf"] > result.chunks[1]["rrf"]
    session.execute.assert_awaited_once()
    statement = session.execute.await_args.args[0].text
    assert statement.lstrip().startswith("WITH recalled_chunks")
    assert statement.count("UPDATE") == 2
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_rerank_model_keeps_rrf_order(monkeypatch):
    pipeline = RetrievalPipeline(
        settings=_settings(rerank_enabled=True, navigation_enabled=False)
    )
    monkeypatch.setattr(pipeline, "_embed_query", AsyncMock(return_value=[0.1] * 8))
    hits = [
        {"id": "a", "content": "A", "vector_score": 0.9},
        {"id": "b", "content": "B", "vector_score": 0.8},
    ]

    with patch(
        "app.core.retrieval.pipeline.vector_search.search", AsyncMock(return_value=hits)
    ), patch(
        "app.core.retrieval.pipeline.fulltext_search.search", AsyncMock(return_value=[])
    ), patch.object(pipeline, "build_reranker", AsyncMock()) as build:
        result = await pipeline.search("q", count_recall=False)

    build.assert_not_called()
    assert result.rerank_triggered is False
    assert result.rerank_skipped_reason == "rerank_model_not_bound"
    assert [chunk["id"] for chunk in result.chunks] == ["a", "b"]


@pytest.mark.asyncio
async def test_explicit_rerank_model_is_loaded_in_provider_layer(monkeypatch):
    pipeline = RetrievalPipeline(
        settings=_settings(rerank_enabled=True, navigation_enabled=False),
        rerank_model={"id": "00000000-0000-0000-0000-000000000011"},
    )
    monkeypatch.setattr(pipeline, "_embed_query", AsyncMock(return_value=[0.1] * 8))
    hits = [
        {"id": "a", "content": "A", "vector_score": 0.9},
        {"id": "b", "content": "B", "vector_score": 0.8},
    ]
    model = object()
    reranker_instance = object()
    get_model = AsyncMock(return_value=model)
    build = AsyncMock(return_value=reranker_instance)
    monkeypatch.setattr("app.core.retrieval.pipeline.get_model_by_id", get_model)
    monkeypatch.setattr(
        "app.core.retrieval.pipeline.build_reranker_from_config", build
    )

    with patch(
        "app.core.retrieval.pipeline.vector_search.search", AsyncMock(return_value=hits)
    ), patch(
        "app.core.retrieval.pipeline.fulltext_search.search", AsyncMock(return_value=[])
    ), patch(
        "app.core.retrieval.pipeline.reranker.rerank",
        AsyncMock(return_value=[{**hits[1], "rerank_score": 1.0}, {**hits[0], "rerank_score": 0.5}]),
    ) as rerank:
        result = await pipeline.search("q", count_recall=False)

    get_model.assert_awaited_once_with(
        "00000000-0000-0000-0000-000000000011", "rerank"
    )
    build.assert_awaited_once_with(model)
    assert result.rerank_triggered is True
    assert result.rerank_skipped_reason is None
    assert [chunk["id"] for chunk in result.chunks] == ["b", "a"]


@pytest.mark.asyncio
async def test_rerank_construction_failure_propagates(monkeypatch):
    pipeline = RetrievalPipeline(
        settings=_settings(rerank_enabled=True, navigation_enabled=False),
        rerank_model={"id": "00000000-0000-0000-0000-000000000011"},
    )
    monkeypatch.setattr(pipeline, "_embed_query", AsyncMock(return_value=[0.1] * 8))
    monkeypatch.setattr(
        "app.core.retrieval.pipeline.get_model_by_id", AsyncMock(return_value=object())
    )
    monkeypatch.setattr(
        "app.core.retrieval.pipeline.build_reranker_from_config",
        AsyncMock(side_effect=RuntimeError("provider down")),
    )
    hits = [
        {"id": "a", "content": "A", "vector_score": 0.9},
        {"id": "b", "content": "B", "vector_score": 0.8},
    ]

    with patch(
        "app.core.retrieval.pipeline.vector_search.search", AsyncMock(return_value=hits)
    ), patch("app.core.retrieval.pipeline.fulltext_search.search", AsyncMock(return_value=[])):
        with pytest.raises(RuntimeError, match="provider down"):
            await pipeline.search("q", count_recall=False)


@pytest.mark.asyncio
async def test_kb_only_search_skips_navigation_and_preserves_hybrid(monkeypatch):
    pipeline = RetrievalPipeline(settings=_settings(navigation_enabled=True))
    monkeypatch.setattr(pipeline, "_embed_query", AsyncMock(return_value=[0.1] * 8))
    hit = {"id": "a", "content": "A", "vector_score": 0.9, "keyword_score": 0.8}

    with patch(
        "app.core.retrieval.pipeline.navigator.navigate", AsyncMock()
    ) as navigation, patch(
        "app.core.retrieval.pipeline.vector_search.search", AsyncMock(return_value=[hit])
    ), patch(
        "app.core.retrieval.pipeline.fulltext_search.search", AsyncMock(return_value=[hit])
    ):
        result = await pipeline.search("q", kb_ids=["kb"], doc_ids=None, count_recall=False)

    navigation.assert_not_called()
    assert result.mode == "hybrid"

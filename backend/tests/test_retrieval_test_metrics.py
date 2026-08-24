"""Pure retrieval quality metric tests."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.retrieval.metadata_filter import MetadataFilter
from app.core.retrieval.test_metrics import (
    aggregate_metrics,
    evaluate_case,
    nearest_rank_percentile,
)
from app.core.retrieval.pipeline import RetrievalResult
from app.exceptions import BizException
from app.models.knowledge_base import KnowledgeBase
from app.models.model_config import ModelConfig
from app.models.retrieval_testing import (
    RetrievalTestCase,
    RetrievalTestCaseResult,
    RetrievalTestRun,
    RetrievalTestSet,
)
from app.services import retrieval_test_service as service


def test_evaluate_case_hit_partial_and_miss():
    result_docs = ["d2", "d1", "d3"]
    assert evaluate_case(["d1"], result_docs, k=3) == {
        "status": "hit",
        "hit_doc_ids": ["d1"],
        "hit_count": 1,
        "recall": 1.0,
        "reciprocal_rank": 0.5,
        "first_hit_rank": 2,
    }
    partial = evaluate_case(["d1", "d4"], result_docs, k=3)
    assert partial["status"] == "partial_hit"
    assert partial["recall"] == 0.5
    miss = evaluate_case(["d4"], result_docs, k=3)
    assert miss["status"] == "miss"
    assert miss["reciprocal_rank"] == 0.0


def test_empty_expected_is_not_evaluated():
    metrics = evaluate_case([], ["d1"], k=3)
    assert metrics == {
        "status": "skipped",
        "hit_doc_ids": [],
        "hit_count": 0,
        "recall": None,
        "reciprocal_rank": None,
        "first_hit_rank": None,
    }


def test_aggregate_multiple_ks_and_latency():
    cases = [
        {"expected_doc_ids": ["d1"], "hit_doc_ids": ["d1"], "status": "hit",
         "recall": 1.0, "reciprocal_rank": 1.0, "latency_ms": 100, "rerank_triggered": True,
         "results": [{"document_id": "d1"}]},
        {"expected_doc_ids": ["d2", "d3"], "hit_doc_ids": ["d2"], "status": "partial_hit",
         "recall": 0.5, "reciprocal_rank": 0.25, "latency_ms": 300, "rerank_triggered": False,
         "results": [{"document_id": "d2"}, {"document_id": "d1"}]},
        {"expected_doc_ids": [], "hit_doc_ids": [], "status": "skipped",
         "recall": None, "reciprocal_rank": None, "latency_ms": 50, "rerank_triggered": False,
         "results": []},
    ]
    metrics = aggregate_metrics(cases, ks=[1, 2])
    assert metrics["case_count"] == 3
    assert metrics["evaluated_case_count"] == 2
    assert metrics["hit_at_k"]["1"] == 1.0
    assert metrics["hit_at_k"]["2"] == 1.0
    assert metrics["recall_at_k"]["2"] == 0.75
    assert metrics["mrr"] == pytest.approx(0.625)
    assert metrics["latency_ms"]["p50"] == 100
    assert metrics["latency_ms"]["p95"] == 300
    assert metrics["rerank_trigger_rate"] == 0.5


def test_aggregate_uses_stored_recall_for_final_k():
    cases = [
        {
            "expected_doc_ids": ["d1"],
            "status": "hit",
            "recall": 0.25,
            "reciprocal_rank": 0.1,
            "results": [{"document_id": "d1"}],
        },
        {
            "expected_doc_ids": ["d2"],
            "status": "hit",
            "recall": 0.75,
            "reciprocal_rank": 0.2,
            "results": [{"document_id": "d2"}],
        },
    ]
    metrics = aggregate_metrics(cases, ks=[1, 5])
    assert metrics["recall_at_k"]["5"] == 0.5
    assert metrics["mrr"] == pytest.approx(0.15)


def test_aggregate_hit_at_k_counts_any_hit_at_every_k():
    cases = [
        {
            "expected_doc_ids": ["d2", "d3"],
            "status": "partial_hit",
            "recall": 0.5,
            "reciprocal_rank": 1.0,
            "results": [{"document_id": "d2"}, {"document_id": "d1"}],
        },
        {
            "expected_doc_ids": ["d4"],
            "status": "miss",
            "recall": 0.0,
            "reciprocal_rank": 0.0,
            "results": [{"document_id": "d1"}],
        },
    ]
    metrics = aggregate_metrics(cases, ks=[1, 2])
    assert metrics["hit_at_k"]["1"] == 0.5
    assert metrics["hit_at_k"]["2"] == 0.5


def test_aggregate_latency_includes_executed_misses_and_skips():
    cases = [
        {"status": "hit", "latency_ms": 100},
        {"status": "miss", "latency_ms": 200},
        {"status": "skipped", "latency_ms": 300},
        {"status": "failed", "latency_ms": 400},
        {"status": "running", "latency_ms": 500},
    ]
    metrics = aggregate_metrics(cases, ks=[1])
    assert metrics["latency_ms"]["p50"] == 200
    assert metrics["latency_ms"]["p95"] == 300


def test_nearest_rank_percentile_uses_1_based_ceil_rank():
    assert nearest_rank_percentile([], 50) is None
    assert nearest_rank_percentile([10, 20, 30, 40], 50) == 20
    assert nearest_rank_percentile([10, 20, 30, 40], 95) == 40


class FakeScalars:
    def __init__(self, rows):
        self.rows = list(rows)

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class FakeResult:
    def __init__(self, rows=None, first=None):
        self.rows = list(rows or [])
        self.first_value = first

    def scalars(self):
        return FakeScalars(self.rows)

    def first(self):
        return self.first_value

    def scalar_one_or_none(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, *, runs=None, cases=None, results=None, models=None):
        self.runs = list(runs or [])
        self.cases = list(cases or [])
        self.results = list(results or [])
        self.models = list(models or [])
        self.added = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def execute(self, statement):
        statement_text = str(statement)
        if "retrieval_test_case_results" in statement_text:
            return FakeResult(rows=self.results)
        if "retrieval_test_runs" in statement_text:
            return FakeResult(rows=self.runs)
        if "retrieval_test_cases" in statement_text:
            return FakeResult(rows=self.cases)
        if "model_configs" in statement_text:
            return FakeResult(rows=self.models)
        return FakeResult(rows=[])

    def add(self, item):
        self.added.append(item)

    def add_all(self, items):
        self.added.extend(items)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _item):
        return None


def _effective():
    values = {
        "method": "hybrid",
        "final_top_k": 5,
        "vector_top_k": 20,
        "keyword_top_k": 20,
        "similarity_threshold": 0.0,
        "vector_weight": 0.7,
        "keyword_weight": 0.3,
        "rrf_k": 60,
        "rerank_enabled": False,
        "rerank_top_n": 10,
        "rerank_trigger_threshold": 0.02,
        "navigation_enabled": False,
        "nav_anchor_count": 3,
        "nav_confidence_threshold": 0.15,
    }
    return {
        "values": {key: {"value": value, "source": "test"} for key, value in values.items()},
        "resolved": values,
    }


def _start_fixture():
    user_id = uuid.uuid4()
    embed = ModelConfig(
        id=uuid.uuid4(),
        grp="embed",
        name="safe-embed",
        prov="openai",
        use="retrieval",
        url="http://embedding.invalid",
        api_key_enc="secret",
        params={"dim": 1024},
        enabled=True,
    )
    rerank = ModelConfig(
        id=uuid.uuid4(),
        grp="rerank",
        name="safe-rerank",
        prov="openai",
        use="rerank",
        url="http://rerank.invalid",
        api_key_enc="secret",
        params={"secret": True},
        enabled=True,
    )
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        user_id=user_id,
        name="Run KB",
        scene="general",
        embedding_model_id=embed.id,
        rerank_model_id=rerank.id,
    )
    test_set = RetrievalTestSet(id=uuid.uuid4(), kb_id=kb.id, name="Run set")
    cases = [
        RetrievalTestCase(
            id=uuid.uuid4(),
            test_set_id=test_set.id,
            query="hit query",
            expected_doc_ids=["doc-hit"],
            expected_chunk_ids=[],
            tags=[],
            enabled=True,
            sort_order=1,
        ),
        RetrievalTestCase(
            id=uuid.uuid4(),
            test_set_id=test_set.id,
            query="miss query",
            expected_doc_ids=["doc-none"],
            expected_chunk_ids=[],
            tags=[],
            enabled=True,
            sort_order=2,
        ),
    ]
    return SimpleNamespace(
        user_id=user_id,
        embed=embed,
        rerank=rerank,
        kb=kb,
        test_set=test_set,
        cases=cases,
    )


@pytest.mark.asyncio
async def test_start_run_creates_safe_snapshot_and_pending_results(monkeypatch):
    fixture = _start_fixture()
    session = FakeSession(cases=fixture.cases, models=[fixture.embed, fixture.rerank])
    effective = _effective()
    effective["embedding_model"] = {
        "id": str(fixture.embed.id),
        "name": fixture.embed.name,
        "prov": fixture.embed.prov,
        "url": fixture.embed.url,
        "enabled": True,
    }
    effective["rerank_model"] = {
        "id": str(fixture.rerank.id),
        "name": fixture.rerank.name,
        "prov": fixture.rerank.prov,
        "url": fixture.rerank.url,
        "enabled": True,
    }
    monkeypatch.setattr(
        service, "_set_from", AsyncMock(return_value=fixture.test_set)
    )
    monkeypatch.setattr(
        service,
        "get_effective_settings",
        AsyncMock(return_value=effective),
        raising=False,
    )
    monkeypatch.setattr(service, "async_session", lambda: session)
    monkeypatch.setattr(
        service,
        "metadata_service",
        SimpleNamespace(list_fields=AsyncMock(return_value=[])),
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "build_sql_predicates",
        MagicMock(),
        raising=False,
    )

    run = await service.start_run(
        test_set_id=fixture.test_set.id,
        user_id=fixture.user_id,
        case_ids=[str(fixture.cases[0].id), str(fixture.cases[1].id)],
        ks=[5, 3],
        override_config={"vector_top_k": 9},
        document_metadata={"source": ["tender"]},
        chunk_metadata={"status": ["active"]},
    )

    assert run.status == "pending"
    assert run.kb_id == fixture.kb.id
    assert run.total_cases == 2
    assert run.override_config == {"vector_top_k": 9}
    assert run.config_snapshot["ks"] == [3, 5]
    assert run.config_snapshot["settings"] == {
        "values": effective["values"],
        "resolved": effective["resolved"],
    }
    assert run.config_snapshot["embedding_model"] == {
        "id": str(fixture.embed.id),
        "name": "safe-embed",
        "prov": "openai",
        "dim": 1024,
    }
    assert run.config_snapshot["rerank_model"] == {
        "id": str(fixture.rerank.id),
        "name": "safe-rerank",
        "prov": "openai",
    }
    assert run.config_snapshot["document_metadata"] == {"source": ["tender"]}
    assert run.config_snapshot["chunk_metadata"] == {"status": ["active"]}
    assert "url" not in str(run.config_snapshot)
    assert "api_key" not in str(run.config_snapshot)
    assert "secret" not in str(run.config_snapshot)
    assert [item.query for item in session.added[1:]] == ["hit query", "miss query"]
    assert {item.status for item in session.added[1:]} == {"pending"}
    assert session.commits == 1
    assert run._newly_created is True


@pytest.mark.asyncio
async def test_duplicate_start_returns_active_run_without_changes(monkeypatch):
    fixture = _start_fixture()
    active = RetrievalTestRun(
        id=uuid.uuid4(),
        test_set_id=fixture.test_set.id,
        kb_id=fixture.kb.id,
        status="running",
        config_snapshot={"existing": True},
        override_config={"existing": True},
        total_cases=2,
        completed_cases=1,
    )
    session = FakeSession(runs=[active], cases=fixture.cases)
    monkeypatch.setattr(
        service, "_set_from", AsyncMock(return_value=fixture.test_set)
    )
    monkeypatch.setattr(service, "async_session", lambda: session)

    duplicate = await service.start_run(
        test_set_id=fixture.test_set.id,
        user_id=fixture.user_id,
        ks=[3],
        override_config={"vector_top_k": 11},
    )

    assert duplicate is active
    assert duplicate.config_snapshot == {"existing": True}
    assert duplicate.override_config == {"existing": True}
    assert duplicate.status == "running"
    assert session.added == []
    assert session.commits == 0
    assert duplicate._newly_created is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ks", "message"),
    [
        ([], "ks cannot be empty"),
        ([3, 3], "ks cannot contain duplicates"),
        ([3, "5"], "ks must be an integer list"),
        ([101], "ks must be between 1 and 100"),
    ],
)
async def test_start_run_validates_cases_and_ks(monkeypatch, ks, message):
    fixture = _start_fixture()
    session = FakeSession(cases=fixture.cases)
    monkeypatch.setattr(
        service, "_set_from", AsyncMock(return_value=fixture.test_set)
    )
    monkeypatch.setattr(service, "async_session", lambda: session)

    with pytest.raises(BizException, match=message):
        await service.start_run(
            test_set_id=fixture.test_set.id,
            user_id=fixture.user_id,
            ks=ks,
        )

    empty = FakeSession(cases=[])
    monkeypatch.setattr(service, "async_session", lambda: empty)
    with pytest.raises(BizException, match="No enabled retrieval test cases"):
        await service.start_run(
            test_set_id=fixture.test_set.id,
            user_id=fixture.user_id,
        )


@pytest.mark.asyncio
async def test_cancel_run_skips_unfinished_results(monkeypatch):
    fixture = _start_fixture()
    run = RetrievalTestRun(
        id=uuid.uuid4(),
        test_set_id=fixture.test_set.id,
        kb_id=fixture.kb.id,
        status="running",
        total_cases=3,
        completed_cases=1,
    )
    results = [
        RetrievalTestCaseResult(
            id=uuid.uuid4(), run_id=run.id, query="a", status="running"
        ),
        RetrievalTestCaseResult(
            id=uuid.uuid4(), run_id=run.id, query="b", status="pending"
        ),
        RetrievalTestCaseResult(
            id=uuid.uuid4(), run_id=run.id, query="c", status="hit"
        ),
    ]
    session = FakeSession(results=results)
    monkeypatch.setattr(
        service,
        "_run_from",
        AsyncMock(return_value=(run, fixture.test_set)),
        raising=False,
    )
    monkeypatch.setattr(service, "async_session", lambda: session)

    canceled = await service.cancel_run(run.id, fixture.user_id)

    assert canceled is run
    assert run.status == "canceled"
    assert run.finished_at is not None
    assert run.completed_cases == 3
    assert [item.status for item in results] == ["skipped", "skipped", "hit"]


def _execute_fixture(models):
    fixture = _start_fixture()
    if models is None:
        models = [fixture.embed, fixture.rerank]
    run = RetrievalTestRun(
        id=uuid.uuid4(),
        test_set_id=fixture.test_set.id,
        kb_id=fixture.kb.id,
        status="pending",
        config_snapshot={
            "settings": _effective(),
            "ks": [3, 5],
            "embedding_model": {
                "id": str(fixture.embed.id),
                "name": fixture.embed.name,
                "prov": fixture.embed.prov,
                "dim": 1024,
            },
            "rerank_model": {
                "id": str(fixture.rerank.id),
                "name": fixture.rerank.name,
                "prov": fixture.rerank.prov,
            },
            "document_metadata": {"source": ["tender"]},
            "chunk_metadata": {"status": ["active"]},
        },
        total_cases=2,
    )
    results = [
        RetrievalTestCaseResult(
            id=uuid.uuid4(),
            run_id=run.id,
            case_id=fixture.cases[0].id,
            query=fixture.cases[0].query,
            status="pending",
            expected_doc_ids=list(fixture.cases[0].expected_doc_ids),
        ),
        RetrievalTestCaseResult(
            id=uuid.uuid4(),
            run_id=run.id,
            case_id=fixture.cases[1].id,
            query=fixture.cases[1].query,
            status="pending",
            expected_doc_ids=list(fixture.cases[1].expected_doc_ids),
        ),
    ]
    session = FakeSession(runs=[run], results=results, models=models)
    return SimpleNamespace(run=run, results=results, session=session)


def _chunk(document_id, suffix):
    return {
        "id": f"chunk-{suffix}",
        "document_id": document_id,
        "document_name": f"{document_id}.pdf",
        "content": f"content {suffix}",
        "section_path": ["chapter", str(suffix)],
        "page_number": suffix,
        "char_count": 100 + suffix,
        "vector_score": 0.91 - suffix * 0.01,
        "keyword_score": 0.42 - suffix * 0.01,
        "vector_rank": suffix,
        "fulltext_rank": suffix + 1,
        "rrf": 0.032 - suffix * 0.001,
        "metadata": {"source": "tender"},
    }


class FakePipeline:
    searches = []
    side_effects = []

    def __init__(self, *, settings, embedding_model=None, rerank_model=None):
        self.settings = settings
        self.embedding_model = embedding_model
        self.rerank_model = rerank_model

    async def search(self, query, **kwargs):
        type(self).searches.append((query, kwargs))
        effect = type(self).side_effects[len(type(self).searches) - 1]
        if isinstance(effect, Exception):
            raise effect
        return effect


@pytest.mark.asyncio
async def test_execute_run_success_metrics_candidates_and_recall_contract(monkeypatch):
    fixture = _execute_fixture(None)
    first = RetrievalResult(
        chunks=[
            _chunk("doc-hit", 1),
            _chunk("doc-other", 2),
            {**_chunk("doc-third", 3), "rerank_score": 0.9},
        ],
        rerank_triggered=True,
    )
    second = RetrievalResult(chunks=[_chunk("doc-other", 1)])
    FakePipeline.searches = []
    FakePipeline.side_effects = [first, second]
    monkeypatch.setattr(service, "RetrievalPipeline", FakePipeline)
    monkeypatch.setattr(service, "async_session", lambda: fixture.session)

    await service.execute_run(fixture.run.id)

    assert [item[0] for item in FakePipeline.searches] == [
        "hit query",
        "miss query",
    ]
    assert all(
        item[1]
        == {
            "kb_ids": [str(fixture.run.kb_id)],
            "doc_ids": None,
            "scope": None,
            "metadata_filter": MetadataFilter(
                document={"source": ["tender"]},
                chunk={"status": ["active"]},
            ),
            "top_k": 5,
            "enable_nav": False,
            "count_recall": False,
        }
        for item in FakePipeline.searches
    )
    hit, miss = fixture.results
    assert hit.status == "hit"
    assert miss.status == "miss"
    assert hit.hit_doc_ids == ["doc-hit"]
    assert hit.metrics["ks"]["3"]["first_hit_rank"] == 1
    assert hit.metrics["ks"]["5"]["recall"] == 1.0
    assert hit.latency_ms is not None
    assert hit.results[0] == {
        "rank": 1,
        "chunk_id": "chunk-1",
        "document_id": "doc-hit",
        "document_name": "doc-hit.pdf",
        "section_path": ["chapter", "1"],
        "page_number": 1,
        "char_count": 101,
        "vector_score": pytest.approx(0.9),
        "keyword_score": pytest.approx(0.41),
        "vector_rank": 1,
        "keyword_rank": 2,
        "rrf_score": pytest.approx(0.031),
        "rerank_score": None,
        "metadata": {"source": "tender"},
    }
    assert hit.results[2]["rerank_score"] == pytest.approx(0.9)
    assert fixture.run.status == "completed"
    assert fixture.run.completed_cases == 2
    assert fixture.run.metrics["case_count"] == 2
    assert fixture.run.metrics["evaluated_case_count"] == 2
    assert fixture.run.metrics["hit_at_k"] == {"3": 0.5, "5": 0.5}
    assert fixture.run.metrics["mrr"] == pytest.approx(0.5)
    assert fixture.run.metrics["failure_rate"] == 0.0
    assert fixture.session.commits >= 4


@pytest.mark.asyncio
async def test_execute_run_continues_after_single_case_provider_error(monkeypatch):
    fixture = _execute_fixture(None)
    success = RetrievalResult(chunks=[_chunk("doc-hit", 1)])
    FakePipeline.searches = []
    FakePipeline.side_effects = [RuntimeError("rerank provider failed"), success]
    monkeypatch.setattr(service, "RetrievalPipeline", FakePipeline)
    monkeypatch.setattr(service, "async_session", lambda: fixture.session)

    await service.execute_run(fixture.run.id)

    assert len(FakePipeline.searches) == 2
    assert [item.status for item in fixture.results] == ["failed", "miss"]
    assert fixture.results[0].error == "rerank provider failed"
    assert fixture.results[0].latency_ms is not None
    assert fixture.run.status == "completed"
    assert fixture.run.completed_cases == 2
    assert fixture.run.metrics["failure_rate"] == 0.5


@pytest.mark.asyncio
async def test_execute_run_terminal_model_failure_skips_unexecuted_cases(monkeypatch):
    fixture = _execute_fixture(models=[])
    monkeypatch.setattr(
        service,
        "RetrievalPipeline",
        AsyncMock(side_effect=AssertionError("pipeline must not be constructed")),
    )
    monkeypatch.setattr(service, "async_session", lambda: fixture.session)

    await service.execute_run(fixture.run.id)

    assert fixture.run.status == "failed"
    assert fixture.run.error == "Embedding model is unavailable"
    assert fixture.run.finished_at is not None
    assert [item.status for item in fixture.results] == ["skipped", "skipped"]


@pytest.mark.asyncio
async def test_execute_run_unconfigured_default_embedding_is_terminal(monkeypatch):
    fixture = _execute_fixture(models=[])
    fixture.run.config_snapshot["embedding_model"] = None
    fixture.run.config_snapshot["rerank_model"] = None

    class UnusedPipeline:
        def __init__(self, **_kwargs):
            pass

        async def search(self, *_args, **_kwargs):
            raise AssertionError("retrieval must not run without an embedding model")

    monkeypatch.setattr(service, "RetrievalPipeline", UnusedPipeline)
    monkeypatch.setattr(
        service,
        "build_embeddings",
        AsyncMock(side_effect=RuntimeError("default embedding unavailable")),
        raising=False,
    )
    monkeypatch.setattr(service, "async_session", lambda: fixture.session)

    await service.execute_run(fixture.run.id)

    assert fixture.run.status == "failed"
    assert fixture.run.error == "Embedding model is unavailable"
    assert [item.status for item in fixture.results] == ["skipped", "skipped"]


@pytest.mark.asyncio
async def test_execute_run_cancellation_wins_before_case_finalization(monkeypatch):
    fixture = _execute_fixture(None)
    success = RetrievalResult(chunks=[_chunk("doc-hit", 1)])

    class CancelingPipeline(FakePipeline):
        async def search(self, query, **kwargs):
            await super().search(query, **kwargs)
            fixture.run.status = "canceled"
            fixture.results[0].status = "skipped"
            return success

    FakePipeline.searches = []
    FakePipeline.side_effects = [success]
    monkeypatch.setattr(service, "RetrievalPipeline", CancelingPipeline)
    monkeypatch.setattr(service, "async_session", lambda: fixture.session)

    await service.execute_run(fixture.run.id)

    assert len(FakePipeline.searches) == 1
    assert fixture.run.status == "canceled"
    assert [item.status for item in fixture.results] == ["skipped", "skipped"]

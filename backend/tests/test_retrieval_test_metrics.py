"""Pure retrieval quality metric tests."""
import pytest

from app.core.retrieval.test_metrics import (
    aggregate_metrics,
    evaluate_case,
    nearest_rank_percentile,
)


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

"""Pure functions for retrieval test quality measurement."""
from math import ceil


def evaluate_case(expected_doc_ids: list[str], result_docs: list[str], *, k: int) -> dict:
    expected = list(dict.fromkeys(map(str, expected_doc_ids)))
    if not expected:
        return {
            "status": "skipped",
            "hit_doc_ids": [],
            "hit_count": 0,
            "recall": None,
            "reciprocal_rank": None,
            "first_hit_rank": None,
        }

    ranked_docs = [str(doc_id) for doc_id in result_docs[:k]]
    hits = [doc_id for doc_id in expected if doc_id in ranked_docs]
    first_rank = next((ranked_docs.index(doc_id) + 1 for doc_id in hits), None)
    recall = len(hits) / len(expected)
    status = "hit" if len(hits) == len(expected) else "partial_hit" if hits else "miss"
    return {
        "status": status,
        "hit_doc_ids": hits,
        "hit_count": len(hits),
        "recall": recall,
        "reciprocal_rank": 1.0 / first_rank if first_rank else 0.0,
        "first_hit_rank": first_rank,
    }


def nearest_rank_percentile(values: list[int | float], percentile: int | float) -> int | float | None:
    """Return the mathematical nearest-rank percentile."""
    if not 0 <= percentile <= 100:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(values)
    if not ordered:
        return None
    rank = max(1, ceil(percentile * len(ordered) / 100))
    return ordered[rank - 1]


def _result_doc_ids(case: dict, k: int) -> list[str]:
    documents = case.get("results") or []
    return [str(item.get("document_id")) for item in documents[:k]]


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def aggregate_metrics(cases: list[dict], ks: list[int]) -> dict:
    evaluated = [case for case in cases if case.get("status") != "skipped"]
    expected_counts = [len(set(map(str, case.get("expected_doc_ids") or []))) for case in evaluated]

    hit_at_k = {}
    recall_at_k = {}
    for k in ks:
        hits = 0
        recalled = 0.0
        for case, expected_count in zip(evaluated, expected_counts):
            expected = set(map(str, case.get("expected_doc_ids") or []))
            found = expected.intersection(_result_doc_ids(case, k))
            hits += bool(found)
            if expected_count:
                recalled += len(found) / expected_count
        hit_at_k[str(k)] = _rate(hits, len(evaluated))
        recall_at_k[str(k)] = _rate(0, 1) if not evaluated else recalled / len(evaluated)

    final_k = max(ks)
    stored_recalls = [
        float(case["recall"])
        for case in evaluated
        if case.get("recall") is not None
    ]
    recall_at_k[str(final_k)] = (
        sum(stored_recalls) / len(stored_recalls) if stored_recalls else 0.0
    )

    valid_rr = [
        float(case["reciprocal_rank"])
        for case in evaluated
        if case.get("reciprocal_rank") is not None
    ]
    mrr = sum(valid_rr) / len(valid_rr) if valid_rr else 0.0

    executed_states = {"hit", "partial_hit", "miss", "skipped"}
    latencies = [
        case["latency_ms"]
        for case in cases
        if case.get("status") in executed_states
        and case.get("latency_ms") is not None
    ]
    rerank_count = sum(bool(case.get("rerank_triggered")) for case in evaluated)
    navigation_count = sum(bool(case.get("navigation_scoped")) for case in evaluated)
    failure_count = sum(case.get("status") == "failed" for case in evaluated)

    return {
        "case_count": len(cases),
        "evaluated_case_count": len(evaluated),
        "hit_at_k": hit_at_k,
        "recall_at_k": recall_at_k,
        "mrr": mrr,
        "latency_ms": {
            "p50": nearest_rank_percentile(latencies, 50),
            "p95": nearest_rank_percentile(latencies, 95),
        },
        "rerank_trigger_rate": _rate(rerank_count, len(evaluated)),
        "navigation_scoped_rate": _rate(navigation_count, len(evaluated)),
        "failure_rate": _rate(failure_count, len(evaluated)),
    }

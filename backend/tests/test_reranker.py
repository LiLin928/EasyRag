"""Reranker 测试。"""
import pytest
from app.core.retrieval.reranker import should_rerank


def test_should_rerank_true():
    """测试应该触发 rerank 的情况。"""
    fused = [
        {"rrf_score": 0.8},
        {"rrf_score": 0.75},  # 差值 0.05 < 0.1
    ]

    assert should_rerank(fused, threshold=0.1) == True


def test_should_rerank_false():
    """测试不应该触发 rerank 的情况。"""
    fused = [
        {"rrf_score": 0.8},
        {"rrf_score": 0.5},  # 差值 0.3 > 0.1
    ]

    assert should_rerank(fused, threshold=0.1) == False


def test_should_rerank_single_item():
    """测试只有一个结果的情况。"""
    fused = [{"rrf_score": 0.8}]

    assert should_rerank(fused, threshold=0.1) == False


def test_should_rerank_empty():
    """测试空结果的情况。"""
    fused = []

    assert should_rerank(fused, threshold=0.1) == False
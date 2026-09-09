"""混合检索和 RRF 测试。"""
import pytest
from app.core.retrieval.rrf import rrf_fusion, weighted_fusion


def test_rrf_fusion_basic():
    """测试基本 RRF 融合。"""
    vector_results = [
        {"chunk_id": "1", "rank": 1, "vector_score": 0.9, "keyword_score": 0.0},
        {"chunk_id": "2", "rank": 2, "vector_score": 0.8, "keyword_score": 0.0},
    ]

    keyword_results = [
        {"chunk_id": "2", "rank": 1, "vector_score": 0.0, "keyword_score": 0.95},
        {"chunk_id": "3", "rank": 2, "vector_score": 0.0, "keyword_score": 0.85},
    ]

    fused = rrf_fusion(vector_results, keyword_results, k=60)

    # 验证结果
    assert len(fused) == 3

    # 验证排名
    assert all("rank" in r for r in fused)
    assert all("rrf_score" in r for r in fused)
    assert all("final_score" in r for r in fused)

    # 验证第一个结果的分数最高
    assert fused[0]["rank"] == 1
    assert fused[0]["rrf_score"] > 0

    # chunk_id "2" 在两个列表中都有，应该排在前面
    assert fused[0]["chunk_id"] == "2"


def test_rrf_fusion_empty():
    """测试空结果融合。"""
    fused = rrf_fusion([], [], k=60)
    assert len(fused) == 0


def test_rrf_fusion_single_list():
    """测试单个列表融合。"""
    vector_results = [
        {"chunk_id": "1", "rank": 1, "vector_score": 0.9, "keyword_score": 0.0},
    ]

    fused = rrf_fusion(vector_results, [], k=60)

    assert len(fused) == 1
    assert fused[0]["chunk_id"] == "1"


def test_weighted_fusion_basic():
    """测试加权融合。"""
    vector_results = [
        {"chunk_id": "1", "rank": 1, "vector_score": 0.9, "keyword_score": 0.0},
        {"chunk_id": "2", "rank": 2, "vector_score": 0.8, "keyword_score": 0.0},
    ]

    keyword_results = [
        {"chunk_id": "2", "rank": 1, "vector_score": 0.0, "keyword_score": 0.95},
        {"chunk_id": "3", "rank": 2, "vector_score": 0.0, "keyword_score": 0.85},
    ]

    fused = weighted_fusion(vector_results, keyword_results, vector_weight=0.7, keyword_weight=0.3)

    # 验证结果
    assert len(fused) == 3
    assert all("rank" in r for r in fused)
    assert all("weighted_score" in r for r in fused)
    assert all("final_score" in r for r in fused)
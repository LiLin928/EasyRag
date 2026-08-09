"""rrf_merge（RRF 融合）单元测试。"""
from app.core.retrieval.rrf_merge import merge


def test_merge_rank_fusion():
    """两路都命中的文档 RRF 分数最高，排首位；结果含全部唯一 id。"""
    vec = [{"id": "a", "content": "A"}, {"id": "b", "content": "B"}]
    kw = [{"id": "b", "content": "B"}, {"id": "c", "content": "C"}]
    fused = merge(vec, kw, w_vec=0.7, w_kw=0.3, k=60)
    ids = [f["id"] for f in fused]
    assert ids[0] == "b"          # 两路都命中，RRF 最高
    assert set(ids) == {"a", "b", "c"}
    assert "rrf" in fused[0]


def test_empty():
    """两路均空时返回空列表。"""
    assert merge([], []) == []

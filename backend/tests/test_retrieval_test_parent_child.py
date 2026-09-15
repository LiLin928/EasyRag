"""召回测试父子分段支持的回归测试。

回归：父子分段知识库的召回测试每条用例都 0 命中，因为测试运行走
RetrievalPipeline（查 chunks 表），而父子库的分段在 child_chunks 表。
本测试覆盖新增的两个纯函数辅助：模式解析与父子候选归一化。
"""
from app.services.retrieval_test_service import (
    _normalize_parent_child_candidates,
    _resolve_retrieval_mode,
)


def test_resolve_retrieval_mode_override_wins():
    """显式 override 优先于 KB 自身模式。"""
    assert _resolve_retrieval_mode("parent_child", "traditional") == "traditional"
    assert _resolve_retrieval_mode("traditional", "parent_child") == "parent_child"


def test_resolve_retrieval_mode_falls_back_to_kb():
    """无 override 时用 KB 的检索模式。"""
    assert _resolve_retrieval_mode("parent_child", None) == "parent_child"
    assert _resolve_retrieval_mode("traditional", None) == "traditional"


def test_resolve_retrieval_mode_default_traditional():
    """KB 模式缺失时默认 traditional。"""
    assert _resolve_retrieval_mode(None, None) == "traditional"
    assert _resolve_retrieval_mode("", None) == "traditional"


def test_normalize_parent_child_candidates_maps_score_to_vector_score():
    """父子检索结果用 score 字段，需映射为候选的 vector_score。"""
    pc_results = [
        {
            "id": "node-1",
            "document_id": "doc-1",
            "document_name": "doc.pdf",
            "title": "第一章",
            "content": "父分段完整内容",
            "score": 0.82,
            "section_path": "第一章",
            "children": [{"id": "c1", "position": 1, "content": "子分段", "score": 0.82}],
        },
    ]
    candidates = _normalize_parent_child_candidates(pc_results)
    assert len(candidates) == 1
    c = candidates[0]
    assert c["rank"] == 1
    assert c["chunk_id"] == "node-1"
    assert c["document_id"] == "doc-1"
    assert c["document_name"] == "doc.pdf"
    assert c["section_path"] == "第一章"
    assert c["content"] == "父分段完整内容"
    assert c["vector_score"] == 0.82
    assert c["metadata"] == {}


def test_normalize_parent_child_candidates_empty():
    assert _normalize_parent_child_candidates([]) == []

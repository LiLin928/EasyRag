"""Chunker（结构化分块）单元测试。"""
from app.core.parser.chunker import chunk
from app.core.parser.models import ParsedElement


def test_chunk_by_section_and_size():
    """超过 chunk_size 的节应切多块；块含 section_path；子节标题进 section_path。"""
    elems = [
        ParsedElement("heading", "第一章", 1, level=1),
        ParsedElement("text", "A" * 600, 1),      # 超过 512，应切多块
        ParsedElement("heading", "1.1 概述", 2, level=2),
        ParsedElement("text", "B" * 100, 2),
    ]
    out = chunk(elems, chunk_size=512, overlap=64)
    assert len(out) >= 2
    assert all("section_path" in c for c in out)
    # 1.1 概述 下的块 section_path 应含 "1.1 概述"
    assert any("1.1 概述" in c["section_path"] for c in out)


def test_empty_elements():
    """空元素列表应返回空。"""
    assert chunk([], 512, 64) == []

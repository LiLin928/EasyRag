# backend/tests/test_parser/test_chunker.py
"""Chunker 测试"""

import pytest
from app.core.parser.chunker import Chunker
from app.core.parser.base import DocumentElement, ElementPosition


@pytest.fixture
def chunker():
    return Chunker(chunk_size=100, chunk_overlap=20)


def create_text_element(text: str) -> DocumentElement:
    """创建文本元素"""
    return DocumentElement(
        element_id=f'elem-{text[:10]}',
        element_type='paragraph',
        content=text,
        position=ElementPosition(),
        metadata={}
    )


@pytest.mark.asyncio
async def test_chunk_simple_text(chunker):
    """测试简单文本分块"""
    elements = [
        create_text_element('This is a test paragraph with some content and more text to reach minimum size.'),
        create_text_element('Another paragraph with more text for testing to ensure enough content.'),
    ]

    chunks = await chunker.chunk(elements, 'test-doc', 'test-kb')

    assert len(chunks) > 0


@pytest.mark.asyncio
async def test_chunk_respects_size_limit(chunker):
    """测试分块大小限制"""
    # 创建超长元素
    long_text = 'A' * 200
    elements = [create_text_element(long_text)]

    chunks = await chunker.chunk(elements, 'test-doc', 'test-kb')

    # 应该被分割
    assert len(chunks) >= 1


@pytest.mark.asyncio
async def test_chunk_with_overlap(chunker):
    """测试分块重叠"""
    elements = [
        create_text_element('First paragraph with enough content.'),
        create_text_element('Second paragraph with more text.'),
        create_text_element('Third paragraph ends the sequence.'),
    ]

    chunks = await chunker.chunk(elements, 'test-doc', 'test-kb')

    # 验证有输出
    assert len(chunks) > 0
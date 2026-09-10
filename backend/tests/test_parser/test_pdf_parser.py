# backend/tests/test_parser/test_pdf_parser.py
"""PDF 解析器测试"""

import pytest
from app.core.parser.pdf_parser import PDFParser
from app.core.parser.base import ParsedDocument


@pytest.fixture
def parser():
    """创建解析器实例"""
    return PDFParser()


@pytest.mark.asyncio
async def test_parse_simple_pdf(parser):
    """测试解析简单 PDF"""
    with open('tests/fixtures/documents/pdf/simple.pdf', 'rb') as f:
        file_data = f.read()

    result = await parser.parse(file_data, 'test-doc')

    assert isinstance(result, ParsedDocument)
    assert result.doc_id == 'test-doc'
    assert len(result.elements) > 0
    assert all(elem.element_type in ['paragraph', 'heading'] for elem in result.elements)


@pytest.mark.asyncio
async def test_parse_chinese_pdf(parser):
    """测试解析中文 PDF"""
    with open('tests/fixtures/documents/pdf/chinese.pdf', 'rb') as f:
        file_data = f.read()

    result = await parser.parse(file_data, 'test-doc')

    assert len(result.elements) > 0
    # 验证包含中文
    has_chinese = any(
        '一' <= char <= '鿿'
        for elem in result.elements
        for char in elem.content
    )
    assert has_chinese


@pytest.mark.asyncio
async def test_extract_metadata(parser):
    """测试元数据提取"""
    with open('tests/fixtures/documents/pdf/simple.pdf', 'rb') as f:
        file_data = f.read()

    result = await parser.parse(file_data, 'test-doc')

    assert 'file_size' in result.metadata
    assert 'parse_time' in result.metadata
    assert 'page_count' in result.metadata
    assert result.metadata['page_count'] > 0
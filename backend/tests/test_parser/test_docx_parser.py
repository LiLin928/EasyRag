# backend/tests/test_parser/test_docx_parser.py
"""DOCX 解析器测试"""

import pytest
from app.core.parser.docx_parser import DOCXParser
from app.core.parser.base import ParsedDocument


@pytest.fixture
def parser():
    return DOCXParser()


@pytest.mark.asyncio
async def test_parse_simple_docx(parser):
    """测试解析简单 DOCX"""
    with open('tests/fixtures/documents/docx/simple.docx', 'rb') as f:
        file_data = f.read()

    result = await parser.parse(file_data, 'test-doc')

    assert isinstance(result, ParsedDocument)
    assert result.doc_id == 'test-doc'
    assert len(result.elements) > 0


@pytest.mark.asyncio
async def test_heading_recognition(parser):
    """测试标题识别"""
    with open('tests/fixtures/documents/docx/simple.docx', 'rb') as f:
        file_data = f.read()

    result = await parser.parse(file_data, 'test-doc')

    # 应该有标题元素
    headings = [e for e in result.elements if e.element_type == 'heading']
    assert len(headings) > 0


@pytest.mark.asyncio
async def test_paragraph_extraction(parser):
    """测试段落提取"""
    with open('tests/fixtures/documents/docx/simple.docx', 'rb') as f:
        file_data = f.read()

    result = await parser.parse(file_data, 'test-doc')

    # 应该有段落元素
    paragraphs = [e for e in result.elements if e.element_type == 'paragraph']
    assert len(paragraphs) > 0
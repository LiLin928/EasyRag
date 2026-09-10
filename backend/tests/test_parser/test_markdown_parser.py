# backend/tests/test_parser/test_markdown_parser.py
"""Markdown 解析器测试"""

import pytest
from app.core.parser.markdown_parser import MarkdownParser
from app.core.parser.base import ParsedDocument


@pytest.fixture
def parser():
    return MarkdownParser()


@pytest.mark.asyncio
async def test_parse_simple_markdown(parser):
    """测试解析简单 Markdown"""
    with open('tests/fixtures/documents/md/simple.md', 'r', encoding='utf-8') as f:
        file_content = f.read()

    result = await parser.parse(file_content.encode('utf-8'), 'test-doc')

    assert isinstance(result, ParsedDocument)
    assert len(result.elements) > 0


@pytest.mark.asyncio
async def test_heading_extraction(parser):
    """测试标题提取"""
    with open('tests/fixtures/documents/md/simple.md', 'r', encoding='utf-8') as f:
        file_content = f.read()

    result = await parser.parse(file_content.encode('utf-8'), 'test-doc')

    headings = [e for e in result.elements if e.element_type == 'heading']
    assert len(headings) > 0


@pytest.mark.asyncio
async def test_list_extraction(parser):
    """测试列表提取"""
    with open('tests/fixtures/documents/md/simple.md', 'r', encoding='utf-8') as f:
        file_content = f.read()

    result = await parser.parse(file_content.encode('utf-8'), 'test-doc')

    lists = [e for e in result.elements if e.element_type == 'list']
    assert len(lists) > 0
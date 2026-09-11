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


@pytest.mark.asyncio
async def test_table_extraction(parser):
    """测试表格提取

    验证：
    1. 表格被识别为 table 元素类型
    2. 表格作为整体单元，不被逐行拆分
    3. 表格内容完整
    """
    markdown_with_table = '''# 文档标题

这是一个段落。

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A   | B   | C   |
| D   | E   | F   |

这是另一个段落。

| 姓名 | 年龄 |
|------|------|
| 张三 | 25   |
| 李四 | 30   |
'''

    result = await parser.parse(markdown_with_table.encode('utf-8'), 'test-doc')

    # 验证有表格元素
    table_elements = [e for e in result.elements if e.element_type == 'table']
    assert len(table_elements) == 2, f"期望 2 个表格，实际 {len(table_elements)} 个"

    # 验证第一个表格内容完整
    first_table = table_elements[0]
    assert '| 列1 | 列2 | 列3 |' in first_table.content
    assert '| A   | B   | C   |' in first_table.content
    assert '| D   | E   | F   |' in first_table.content

    # 验证表格没有被拆分成多个段落
    paragraph_elements = [e for e in result.elements if e.element_type == 'paragraph']
    # 应该只有 2 个段落（不包括表格行）
    assert len(paragraph_elements) == 2, f"期望 2 个段落，实际 {len(paragraph_elements)} 个"

    # 验证元素数量合理（不应该有太多元素）
    # 应该包含：1 标题 + 2 段落 + 2 表格 = 5 个元素
    assert len(result.elements) <= 6, f"元素数量过多: {len(result.elements)}"


@pytest.mark.asyncio
async def test_table_with_separator_rows(parser):
    """测试表格分隔符行处理

    验证分隔符行（|-----|）不被当作独立元素
    """
    markdown_content = '''| 标题1 | 标题2 |
|-------|-------|
| 内容1 | 内容2 |
'''

    result = await parser.parse(markdown_content.encode('utf-8'), 'test-doc')

    # 应该只有 1 个表格元素
    table_elements = [e for e in result.elements if e.element_type == 'table']
    assert len(table_elements) == 1

    # 验证分隔符行在表格内部
    table = table_elements[0]
    assert '|-------|-------|' in table.content

    # 验证没有独立的段落元素（分隔符行不应该被当作段落）
    paragraph_elements = [e for e in result.elements if e.element_type == 'paragraph']
    assert len(paragraph_elements) == 0


@pytest.mark.asyncio
async def test_table_metadata(parser):
    """测试表格元数据

    验证表格元素的 metadata 包含正确的行数统计
    """
    markdown_content = '''| A | B |
|---|---|
| 1 | 2 |
| 3 | 4 |
| 5 | 6 |
'''

    result = await parser.parse(markdown_content.encode('utf-8'), 'test-doc')

    table_elements = [e for e in result.elements if e.element_type == 'table']
    assert len(table_elements) == 1

    table = table_elements[0]
    # 验证 metadata 包含行数（不包括表头和分隔符行）
    if 'rows' in table.metadata:
        assert table.metadata['rows'] == 3  # 3 行数据
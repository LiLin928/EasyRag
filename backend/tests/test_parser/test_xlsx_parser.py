# backend/tests/test_parser/test_xlsx_parser.py
"""XLSX 解析器测试"""

import pytest
from app.core.parser.xlsx_parser import XLSXParser
from app.core.parser.base import ParsedDocument


@pytest.fixture
def parser():
    return XLSXParser()


@pytest.mark.asyncio
async def test_parse_simple_xlsx(parser):
    """测试解析简单 XLSX"""
    with open('tests/fixtures/documents/xlsx/simple.xlsx', 'rb') as f:
        file_data = f.read()

    result = await parser.parse(file_data, 'test-doc')

    assert isinstance(result, ParsedDocument)
    assert len(result.elements) > 0


@pytest.mark.asyncio
async def test_sheet_extraction(parser):
    """测试工作表提取"""
    with open('tests/fixtures/documents/xlsx/simple.xlsx', 'rb') as f:
        file_data = f.read()

    result = await parser.parse(file_data, 'test-doc')

    # 应该有表格元素
    tables = [e for e in result.elements if e.element_type == 'table']
    assert len(tables) > 0
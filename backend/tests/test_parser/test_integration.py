# backend/tests/test_parser/test_integration.py
"""集成测试"""

import pytest
from app.core.parser.dispatcher import DocumentDispatcher
from app.core.parser.tree_builder import TreeBuilder
from app.core.parser.chunker import Chunker


@pytest.mark.asyncio
async def test_pdf_full_pipeline():
    """测试 PDF 完整流程"""
    with open('tests/fixtures/documents/pdf/simple.pdf', 'rb') as f:
        file_data = f.read()

    # 1. 解析
    dispatcher = DocumentDispatcher()
    parsed_doc = await dispatcher._dispatch_from_data(
        file_data, 'test.pdf', 'test-doc'
    )

    assert len(parsed_doc.elements) > 0

    # 2. 构建树
    tree_builder = TreeBuilder()
    tree = await tree_builder.build(parsed_doc.elements, 'test-doc')

    assert tree is not None

    # 3. 分块
    chunker = Chunker()
    chunks = await chunker.chunk(parsed_doc.elements, 'test-doc', 'test-kb')

    # 验证完整流程
    assert len(parsed_doc.elements) > 0
    assert tree is not None


@pytest.mark.asyncio
async def test_docx_full_pipeline():
    """测试 DOCX 完整流程"""
    with open('tests/fixtures/documents/docx/simple.docx', 'rb') as f:
        file_data = f.read()

    dispatcher = DocumentDispatcher()
    parsed_doc = await dispatcher._dispatch_from_data(
        file_data, 'test.docx', 'test-doc'
    )

    assert len(parsed_doc.elements) > 0
    assert any(e.element_type == 'heading' for e in parsed_doc.elements)


@pytest.mark.asyncio
async def test_markdown_full_pipeline():
    """测试 Markdown 完整流程"""
    with open('tests/fixtures/documents/md/simple.md', 'r', encoding='utf-8') as f:
        file_data = f.read().encode('utf-8')

    dispatcher = DocumentDispatcher()
    parsed_doc = await dispatcher._dispatch_from_data(
        file_data, 'test.md', 'test-doc'
    )

    assert len(parsed_doc.elements) > 0

    # 验证标题提取
    headings = [e for e in parsed_doc.elements if e.element_type == 'heading']
    assert len(headings) > 0


@pytest.mark.asyncio
async def test_xlsx_full_pipeline():
    """测试 XLSX 完整流程"""
    with open('tests/fixtures/documents/xlsx/simple.xlsx', 'rb') as f:
        file_data = f.read()

    dispatcher = DocumentDispatcher()
    parsed_doc = await dispatcher._dispatch_from_data(
        file_data, 'test.xlsx', 'test-doc'
    )

    assert len(parsed_doc.elements) > 0
    assert all(e.element_type == 'table' for e in parsed_doc.elements)


@pytest.mark.asyncio
async def test_all_parsers_via_dispatcher():
    """测试 Dispatcher 支持所有格式"""
    dispatcher = DocumentDispatcher()

    # 测试 PDF
    assert dispatcher._get_parser_for_extension('pdf').__class__.__name__ == 'PDFParser'

    # 测试 DOCX
    assert dispatcher._get_parser_for_extension('docx').__class__.__name__ == 'DOCXParser'

    # 测试 XLSX
    assert dispatcher._get_parser_for_extension('xlsx').__class__.__name__ == 'XLSXParser'

    # 测试 Markdown
    assert dispatcher._get_parser_for_extension('md').__class__.__name__ == 'MarkdownParser'
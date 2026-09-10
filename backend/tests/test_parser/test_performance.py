# backend/tests/test_parser/test_performance.py
"""性能测试"""

import pytest
import time
from app.core.parser.dispatcher import DocumentDispatcher


@pytest.mark.asyncio
async def test_pdf_parse_performance():
    """测试 PDF 解析性能 (< 30秒)"""
    with open('tests/fixtures/documents/pdf/simple.pdf', 'rb') as f:
        file_data = f.read()

    dispatcher = DocumentDispatcher()

    start = time.time()
    await dispatcher._dispatch_from_data(file_data, 'test.pdf', 'test-doc')
    elapsed = time.time() - start

    assert elapsed < 30, f"Parse took {elapsed}s, expected < 30s"
    print(f"\nPDF parse time: {elapsed:.2f}s")


@pytest.mark.asyncio
async def test_docx_parse_performance():
    """测试 DOCX 解析性能 (< 10秒)"""
    with open('tests/fixtures/documents/docx/simple.docx', 'rb') as f:
        file_data = f.read()

    dispatcher = DocumentDispatcher()

    start = time.time()
    await dispatcher._dispatch_from_data(file_data, 'test.docx', 'test-doc')
    elapsed = time.time() - start

    assert elapsed < 10, f"Parse took {elapsed}s, expected < 10s"
    print(f"\nDOCX parse time: {elapsed:.2f}s")


@pytest.mark.asyncio
async def test_xlsx_parse_performance():
    """测试 XLSX 解析性能 (< 10秒)"""
    with open('tests/fixtures/documents/xlsx/simple.xlsx', 'rb') as f:
        file_data = f.read()

    dispatcher = DocumentDispatcher()

    start = time.time()
    await dispatcher._dispatch_from_data(file_data, 'test.xlsx', 'test-doc')
    elapsed = time.time() - start

    assert elapsed < 10, f"Parse took {elapsed}s, expected < 10s"
    print(f"\nXLSX parse time: {elapsed:.2f}s")


@pytest.mark.asyncio
async def test_markdown_parse_performance():
    """测试 Markdown 解析性能 (< 5秒)"""
    with open('tests/fixtures/documents/md/simple.md', 'r', encoding='utf-8') as f:
        file_data = f.read().encode('utf-8')

    dispatcher = DocumentDispatcher()

    start = time.time()
    await dispatcher._dispatch_from_data(file_data, 'test.md', 'test-doc')
    elapsed = time.time() - start

    assert elapsed < 5, f"Parse took {elapsed}s, expected < 5s"
    print(f"\nMarkdown parse time: {elapsed:.2f}s")


@pytest.mark.asyncio
async def test_full_pipeline_performance():
    """测试完整管线性能 (< 60秒)"""
    from app.core.parser.tree_builder import TreeBuilder
    from app.core.parser.chunker import Chunker

    with open('tests/fixtures/documents/pdf/simple.pdf', 'rb') as f:
        file_data = f.read()

    start = time.time()

    # 解析
    dispatcher = DocumentDispatcher()
    parsed_doc = await dispatcher._dispatch_from_data(file_data, 'test.pdf', 'test-doc')

    # 构建树
    tree_builder = TreeBuilder()
    tree = await tree_builder.build(parsed_doc.elements, 'test-doc')

    # 分块
    chunker = Chunker()
    chunks = await chunker.chunk(parsed_doc.elements, 'test-doc', 'test-kb')

    elapsed = time.time() - start

    assert elapsed < 60, f"Full pipeline took {elapsed}s, expected < 60s"
    print(f"\nFull pipeline time: {elapsed:.2f}s")
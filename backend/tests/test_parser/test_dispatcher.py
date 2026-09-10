# backend/tests/test_parser/test_dispatcher.py
"""Dispatcher 测试"""

import pytest
from app.core.parser.dispatcher import DocumentDispatcher
from app.core.parser.base import ParsedDocument


@pytest.fixture
def dispatcher():
    return DocumentDispatcher()


@pytest.mark.asyncio
async def test_dispatch_pdf(dispatcher):
    """测试调度 PDF"""
    with open('tests/fixtures/documents/pdf/simple.pdf', 'rb') as f:
        file_data = f.read()

    # 模拟存储（实际应该 mock）
    result = await dispatcher._dispatch_from_data(file_data, 'test.pdf', 'test-doc')

    assert isinstance(result, ParsedDocument)
    assert len(result.elements) > 0


@pytest.mark.asyncio
async def test_dispatch_docx(dispatcher):
    """测试调度 DOCX"""
    with open('tests/fixtures/documents/docx/simple.docx', 'rb') as f:
        file_data = f.read()

    result = await dispatcher._dispatch_from_data(file_data, 'test.docx', 'test-doc')

    assert isinstance(result, ParsedDocument)


@pytest.mark.asyncio
async def test_dispatch_unsupported_format(dispatcher):
    """测试不支持的格式"""
    with pytest.raises(ValueError, match="Unsupported file type"):
        await dispatcher._dispatch_from_data(b'test', 'test.xyz', 'test-doc')


@pytest.mark.asyncio
async def test_parser_selection(dispatcher):
    """测试解析器选择"""
    assert dispatcher._get_parser_for_extension('pdf').__class__.__name__ == 'PDFParser'
    assert dispatcher._get_parser_for_extension('docx').__class__.__name__ == 'DOCXParser'
    assert dispatcher._get_parser_for_extension('xlsx').__class__.__name__ == 'XLSXParser'
    assert dispatcher._get_parser_for_extension('md').__class__.__name__ == 'MarkdownParser'
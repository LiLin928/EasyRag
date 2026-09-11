"""
解决方案 C: 使用 pywin32 + Microsoft Word（仅 Windows）

适用场景：
- Windows 环境
- 已安装 Microsoft Word
- 需要完整的 .doc 支持（保留格式）

优点：
1. 最完整的 .doc 支持
2. 可保留格式、识别标题/列表
3. 使用 Word 的 COM 接口

缺点：
1. 仅 Windows 平台
2. 需要安装 Microsoft Word
3. 性能较低（启动 Word 进程）
4. 不适合服务器环境
"""

# ===== 步骤 1: 添加依赖 =====
# 文件：backend/pyproject.toml

dependencies = [
    # ... 现有依赖
    "pywin32>=305",  # 仅 Windows
]


# ===== 步骤 2: 创建 DOC 解析器 =====
# 文件：backend/app/core/parser/doc_parser_win32.py（新文件）

"""DOC 文档解析器实现（Windows + Word COM）"""

import logging
from typing import List
import asyncio
import platform

from .base import (
    BaseParser,
    ParsedDocument,
    DocumentElement,
    ElementPosition,
)

logger = logging.getLogger(__name__)

# 仅在 Windows 上导入
if platform.system() == 'Windows':
    import win32com.client
    import pythoncom


class DOCParser(BaseParser):
    """DOC 文档解析器（Windows + Word COM）

    使用 Microsoft Word COM 接口解析 .doc 文件。
    仅在 Windows 环境下可用，需要安装 Microsoft Word。
    """

    def __init__(self):
        """检查环境"""
        if platform.system() != 'Windows':
            raise RuntimeError(
                "DOCParser 仅支持 Windows 环境。"
                "在 Linux 上请使用 textract 方案。"
            )

    async def parse(self, file_data: bytes, doc_id: str) -> ParsedDocument:
        """
        解析 DOC 文档

        Args:
            file_data: DOC 文件二进制数据
            doc_id: 文档 ID

        Returns:
            ParsedDocument: 解析结果
        """
        logger.info(f"Starting DOC parsing (Windows COM): doc_id={doc_id}")

        # 在 executor 中运行同步代码
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            self._parse_sync,
            file_data,
            doc_id
        )

        return result

    def _parse_sync(self, file_data: bytes, doc_id: str) -> ParsedDocument:
        """同步解析方法"""

        # 临时保存文件（Word COM 需要文件路径）
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix='.doc', delete=False) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name

        try:
            # 初始化 COM
            pythoncom.CoInitialize()

            # 打开 Word
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False

            try:
                # 打开文档
                doc = word.Documents.Open(tmp_path)

                # 提取元素
                elements: List[DocumentElement] = []
                elem_idx = 0

                for para in doc.Paragraphs:
                    text = para.Range.Text.strip()
                    if not text:
                        continue

                    # 判断元素类型
                    style_name = para.Style.NameLocal if para.Style else ''
                    element_type = self._determine_element_type(style_name)

                    element = DocumentElement(
                        element_id=f'{doc_id}-elem-{elem_idx}',
                        element_type=element_type,
                        content=text,
                        position=ElementPosition(),
                        metadata={
                            'style': style_name,
                            'alignment': str(para.Alignment),
                        }
                    )
                    elements.append(element)
                    elem_idx += 1

                # 元数据
                metadata = self._extract_metadata(file_data)
                metadata.update({
                    'paragraph_count': len(elements),
                    'parser': 'win32com',
                })

                logger.info(f"DOC parsing completed: doc_id={doc_id}, elements={len(elements)}")

                return ParsedDocument(
                    doc_id=doc_id,
                    file_key='',
                    elements=elements,
                    metadata=metadata,
                    structure=None,
                )

            finally:
                # 关闭文档
                doc.Close(False)
                word.Quit()

        finally:
            # 清理临时文件
            os.unlink(tmp_path)
            pythoncom.CoUninitialize()

    def _determine_element_type(self, style_name: str) -> str:
        """判断段落类型"""
        if '标题' in style_name or 'Heading' in style_name:
            return 'heading'
        if '列表' in style_name or 'List' in style_name:
            return 'list'
        return 'paragraph'


# ===== 步骤 3: 更新 dispatcher（条件导入）=====
# 文件：backend/app/core/parser/dispatcher.py

import platform

# 根据平台选择 DOC 解析器
if platform.system() == 'Windows':
    from .doc_parser_win32 import DOCParser
else:
    # 在 Linux 上，使用 textract 或抛出错误
    try:
        from .doc_parser import DOCParser
    except ImportError:
        DOCParser = None

PARSER_MAP: Dict[str, Type[BaseParser]] = {
    'pdf': PDFParser,
    'docx': DOCXParser,
    'doc': DOCParser,  # 根据平台自动选择
    'xlsx': XLSXParser,
    'xls': XLSXParser,
    'md': MarkdownParser,
    'markdown': MarkdownParser,
    'txt': MarkdownParser,
}


# ===== 测试（仅 Windows）=====

import pytest

@pytest.mark.skipif(platform.system() != 'Windows', reason="仅 Windows")
async def test_doc_parsing_windows():
    """测试 DOC 文件解析（Windows）"""

    with open('test.doc', 'rb') as f:
        doc_data = f.read()

    dispatcher = DocumentDispatcher()
    result = await dispatcher._dispatch_from_data(
        doc_data,
        'test.doc',
        'test-doc-id'
    )

    assert len(result.elements) > 0
    # 可以识别标题和列表
    element_types = {e.element_type for e in result.elements}
    assert 'heading' in element_types or 'paragraph' in element_types
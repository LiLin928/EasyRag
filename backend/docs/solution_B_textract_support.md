"""
解决方案 B: 使用 textract 库支持 .doc 文件（推荐长期方案）

适用场景：
- 完整支持 .doc 和 .docx
- 跨平台兼容
- 适合 Linux 服务器环境

依赖：
- pip install textract
- Linux: apt-get install antiword
- macOS: brew install antiword
- Windows: 需安装 antiword 或使用 WSL

实施步骤：
"""

# ===== 步骤 1: 添加依赖 =====
# 文件：backend/pyproject.toml

# 添加到 dependencies：
dependencies = [
    # ... 现有依赖
    "textract>=1.6.5",
]


# ===== 步骤 2: 创建 DOC 解析器 =====
# 文件：backend/app/core/parser/doc_parser.py（新文件）

"""DOC 文档解析器实现"""

import logging
from typing import List
import textract
import io

from .base import (
    BaseParser,
    ParsedDocument,
    DocumentElement,
    ElementPosition,
)

logger = logging.getLogger(__name__)


class DOCParser(BaseParser):
    """DOC 文档解析器

    使用 textract 提取 Word 97-2003 (.doc) 文件内容。
    注意：只能提取纯文本，无法保留格式。
    """

    async def parse(self, file_data: bytes, doc_id: str) -> ParsedDocument:
        """
        解析 DOC 文档

        Args:
            file_data: DOC 文件二进制数据
            doc_id: 文档 ID

        Returns:
            ParsedDocument: 解析结果
        """
        logger.info(f"Starting DOC parsing: doc_id={doc_id}")

        try:
            # 1. 使用 textract 提取文本
            # 注意：textract 是同步的，需要在 executor 中运行
            import asyncio
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None,
                lambda: textract.process(
                    input_file=io.BytesIO(file_data),
                    extension='doc'
                ).decode('utf-8')
            )

            # 2. 按段落分割（简单策略）
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

            # 3. 创建元素
            elements: List[DocumentElement] = []
            for idx, para in enumerate(paragraphs):
                element = DocumentElement(
                    element_id=f'{doc_id}-elem-{idx}',
                    element_type='paragraph',
                    content=para,
                    position=ElementPosition(),
                    metadata={'source': 'textract'}
                )
                elements.append(element)

            # 4. 元数据
            metadata = self._extract_metadata(file_data)
            metadata.update({
                'paragraph_count': len(paragraphs),
                'parser': 'textract',
            })

            logger.info(f"DOC parsing completed: doc_id={doc_id}, elements={len(elements)}")

            return ParsedDocument(
                doc_id=doc_id,
                file_key='',
                elements=elements,
                metadata=metadata,
                structure=None,
            )

        except Exception as e:
            logger.error(f"DOC parsing failed: doc_id={doc_id}, error={e}")
            raise


# ===== 步骤 3: 更新 dispatcher =====
# 文件：backend/app/core/parser/dispatcher.py

from .doc_parser import DOCParser  # 导入新解析器

PARSER_MAP: Dict[str, Type[BaseParser]] = {
    'pdf': PDFParser,
    'docx': DOCXParser,
    'doc': DOCParser,  # ✓ 使用 DOCParser
    'xlsx': XLSXParser,
    'xls': XLSXParser,
    'md': MarkdownParser,
    'markdown': MarkdownParser,
    'txt': MarkdownParser,
}


# ===== 步骤 4: 安装 antiword（Linux/VM） =====
# 在虚拟机 192.168.137.13 上执行：

# Ubuntu/Debian:
# sudo apt-get update
# sudo apt-get install antiword

# 测试：
# antiword test.doc


# ===== 步骤 5: 测试 =====

import pytest
from app.core.parser.dispatcher import DocumentDispatcher
import asyncio

async def test_doc_parsing():
    """测试 DOC 文件解析"""

    # 准备一个真实的 .doc 文件
    with open('test.doc', 'rb') as f:
        doc_data = f.read()

    dispatcher = DocumentDispatcher()
    result = await dispatcher._dispatch_from_data(
        doc_data,
        'test.doc',
        'test-doc-id'
    )

    assert len(result.elements) > 0
    assert all(e.element_type == 'paragraph' for e in result.elements)


# ===== 优缺点分析 =====

优点：
1. ✓ 跨平台支持
2. ✓ 支持 .doc 和 .docx
3. ✓ 依赖简单（antiword 在 Linux 上易安装）

缺点：
1. ✗ 只能提取纯文本，无法保留格式
2. ✗ 无法识别标题、列表等元素类型
3. ✗ Windows 需要额外安装 antiword

适用场景：
- 文本内容为主的文档
- 不需要保留复杂格式
- 服务器环境（Linux/VM）
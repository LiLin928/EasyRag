"""PDF 解析器实现"""

import logging
from typing import List
import fitz  # PyMuPDF

from .base import (
    BaseParser,
    ParsedDocument,
    DocumentElement,
    ElementPosition,
)

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """PDF 文档解析器

    使用 PyMuPDF 提取 PDF 内容，支持：
    - 文本块提取
    - 表格识别（基础）
    - 元数据提取
    """

    async def parse(self, file_data: bytes, doc_id: str) -> ParsedDocument:
        """
        解析 PDF 文档

        Args:
            file_data: PDF 文件二进制数据
            doc_id: 文档 ID

        Returns:
            ParsedDocument: 解析结果，包含所有元素和元数据
        """
        logger.info(f"Starting PDF parsing: doc_id={doc_id}")

        # 1. 打开 PDF
        pdf_document = fitz.open(stream=file_data, filetype='pdf')

        # 2. 提取所有元素
        elements: List[DocumentElement] = []
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]

            # 提取文本块
            blocks = page.get_text('dict')['blocks']
            for block_idx, block in enumerate(blocks):
                if 'lines' in block:  # 文本块
                    element = self._create_text_element(
                        block, block_idx, page_num, doc_id
                    )
                    if element.content.strip():  # 忽略空白元素
                        elements.append(element)

        # 3. 提取元数据
        metadata = self._extract_metadata(file_data)
        metadata.update({
            'page_count': len(pdf_document),
            'author': pdf_document.metadata.get('author', ''),
            'title': pdf_document.metadata.get('title', ''),
            'creator': pdf_document.metadata.get('creator', ''),
        })

        # 4. 关闭文档
        pdf_document.close()

        logger.info(f"PDF parsing completed: doc_id={doc_id}, elements={len(elements)}")

        return ParsedDocument(
            doc_id=doc_id,
            file_key='',  # 由 Dispatcher 填充
            elements=elements,
            metadata=metadata,
            structure=None,  # 后续由 TreeBuilder 构建
        )

    def _create_text_element(
        self,
        block: dict,
        block_idx: int,
        page_num: int,
        doc_id: str
    ) -> DocumentElement:
        """创建文本元素"""
        # 合并所有行的文本
        lines = block.get('lines', [])
        text_parts = []
        for line in lines:
            for span in line.get('spans', []):
                text_parts.append(span.get('text', ''))

        content = ' '.join(text_parts)

        # 提取位置信息
        bbox = block.get('bbox', (0, 0, 0, 0))

        # 判断元素类型（简单规则）
        element_type = self._determine_element_type(block)

        return DocumentElement(
            element_id=f'{doc_id}-elem-{page_num}-{block_idx}',
            element_type=element_type,
            content=content,
            position=ElementPosition(
                page=page_num + 1,  # 页码从 1 开始
                x=bbox[0],
                y=bbox[1],
                width=bbox[2] - bbox[0],
                height=bbox[3] - bbox[1],
            ),
            metadata={
                'font_size': self._get_font_size(block),
                'is_bold': self._is_bold(block),
            }
        )

    def _determine_element_type(self, block: dict) -> str:
        """判断元素类型"""
        # 简单规则：大字体可能是标题
        font_size = self._get_font_size(block)
        if font_size > 14:
            return 'heading'
        return 'paragraph'

    def _get_font_size(self, block: dict) -> float:
        """获取字体大小"""
        lines = block.get('lines', [])
        if not lines:
            return 12.0

        # 取第一个 span 的字体大小
        for line in lines:
            spans = line.get('spans', [])
            if spans:
                return spans[0].get('size', 12.0)

        return 12.0

    def _is_bold(self, block: dict) -> bool:
        """判断是否粗体"""
        lines = block.get('lines', [])
        for line in lines:
            spans = line.get('spans', [])
            for span in spans:
                flags = span.get('flags', 0)
                # PyMuPDF 的粗体标志
                if flags & 16:  # e_text_bold
                    return True
        return False

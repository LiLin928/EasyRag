"""DOCX 解析器实现"""

import logging
from typing import List
from docx import Document
import io

from .base import (
    BaseParser,
    ParsedDocument,
    DocumentElement,
    ElementPosition,
)

logger = logging.getLogger(__name__)


class DOCXParser(BaseParser):
    """DOCX 文档解析器

    使用 python-docx 提取内容，支持：
    - 段落提取
    - 标题识别
    - 列表处理
    """

    async def parse(self, file_data: bytes, doc_id: str) -> ParsedDocument:
        """
        解析 DOCX 文档

        Args:
            file_data: DOCX 文件二进制数据
            doc_id: 文档 ID

        Returns:
            ParsedDocument: 解析结果
        """
        logger.info(f"Starting DOCX parsing: doc_id={doc_id}")

        # 1. 打开文档
        doc = Document(io.BytesIO(file_data))

        # 2. 提取元素
        elements: List[DocumentElement] = []
        elem_idx = 0

        for para in doc.paragraphs:
            if not para.text.strip():
                continue

            element = self._create_paragraph_element(para, elem_idx, doc_id)
            elements.append(element)
            elem_idx += 1

        # 3. 提取元数据
        metadata = self._extract_metadata(file_data)
        metadata.update({
            'paragraph_count': len(doc.paragraphs),
            'core_properties': {
                'author': doc.core_properties.author or '',
                'title': doc.core_properties.title or '',
                'subject': doc.core_properties.subject or '',
            }
        })

        logger.info(f"DOCX parsing completed: doc_id={doc_id}, elements={len(elements)}")

        return ParsedDocument(
            doc_id=doc_id,
            file_key='',
            elements=elements,
            metadata=metadata,
            structure=None,
        )

    def _create_paragraph_element(
        self,
        para,
        elem_idx: int,
        doc_id: str
    ) -> DocumentElement:
        """创建段落元素"""
        # 判断元素类型
        element_type = self._determine_element_type(para)

        return DocumentElement(
            element_id=f'{doc_id}-elem-{elem_idx}',
            element_type=element_type,
            content=para.text,
            position=ElementPosition(),  # DOCX 位置信息有限
            metadata={
                'style': para.style.name if para.style else '',
                'alignment': str(para.alignment) if para.alignment else '',
                'is_heading': element_type == 'heading',
            }
        )

    def _determine_element_type(self, para) -> str:
        """判断段落类型"""
        style_name = para.style.name if para.style else ''

        # 标题样式判断
        if 'Heading' in style_name or 'Title' in style_name:
            return 'heading'

        # 列表判断
        if para.style and 'List' in style_name:
            return 'list'

        return 'paragraph'

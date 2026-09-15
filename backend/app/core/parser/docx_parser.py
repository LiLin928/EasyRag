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

        # 提取标题层级（如果是标题）
        level = 0
        if element_type == 'heading':
            level = self._extract_heading_level(para)

        return DocumentElement(
            element_id=f'{doc_id}-elem-{elem_idx}',
            element_type=element_type,
            content=para.text,
            position=ElementPosition(),  # DOCX 位置信息有限
            metadata={
                'style': para.style.name if para.style else '',
                'alignment': str(para.alignment) if para.alignment else '',
                'is_heading': element_type == 'heading',
                'level': level,  # ← 添加标题层级
            }
        )

    def _determine_element_type(self, para) -> str:
        """判断段落类型

        增强标题识别，支持：
        1. 英文样式：Heading 1, Heading 2, Title
        2. 中文样式：标题, 标题 1, 标题 2
        3. 编号标题：第一章, 一、, 1. 等（通过正则）
        """
        style_name = para.style.name if para.style else ''

        # 标题样式判断（增强版）
        # 支持中英文样式名
        heading_keywords = [
            'Heading', 'Title',  # 英文
            '标题',  # 中文（匹配"标题"、"标题 1"、"标题 2"等）
            'TOC Heading',  # 目录标题
        ]

        for keyword in heading_keywords:
            if keyword.lower() in style_name.lower():
                return 'heading'

        # 列表判断
        if para.style and 'List' in style_name:
            return 'list'

        # 基于内容的标题识别（新增）
        text = para.text.strip()
        if self._is_heading_by_content(text):
            return 'heading'

        return 'paragraph'

    def _extract_heading_level(self, para) -> int:
        """提取标题层级

        优先级：
        1. 样式名称（Heading 1/标题 1）
        2. 内容编号（第一章、1.1.1）

        Args:
            para: 段落对象

        Returns:
            标题层级（1-6），如果不是标题返回 0
        """
        import re

        style_name = para.style.name if para.style else ''
        text = para.text.strip()

        # 1. 从样式名称提取层级
        # 英文样式：Heading 1, Heading 2, ...
        match = re.search(r'Heading\s+(\d+)', style_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # 中文样式：标题 1, 标题 2, ...
        match = re.search(r'标题\s*(\d+)', style_name)
        if match:
            return int(match.group(1))

        # 其他编号样式（Title 通常是一级标题）
        if 'Title' in style_name or style_name == '标题':
            return 1

        # 2. 从内容编号推断层级（注意顺序：先匹配更具体的模式）
        # 数字编号：1.1.1 1.1.2（三级）
        if re.match(r'^\d+\.\d+\.\d+', text):
            return 3

        # 数字编号：1.1 1.2（二级）
        if re.match(r'^\d+\.\d+', text):
            return 2

        # 数字编号：1. 2. 3.（一级）
        if re.match(r'^\d+[\.、\s]', text):
            # 排除列表项
            if len(text) <= 50 and not re.search(r'[；。，]$', text):
                return 1

        # 第一章、第二章（一级）
        if re.match(r'^第[一二三四五六七八九十百]+[章节条款部分]', text):
            return 1

        # 一、二、三、（一级）
        if re.match(r'^[一二三四五六七八九十百]+、', text):
            return 1

        # （一）、（二）、（三）（二级）
        if re.match(r'^（[一二三四五六七八九十百]+）', text):
            return 2

        # 默认：无法识别层级，返回 1
        return 1

    def _is_heading_by_content(self, text: str) -> bool:
        """基于内容判断是否为标题

        识别模式：
        1. 中文编号：第一章、第二章...
        2. 数字编号：一、二、三...
        3. 阿拉伯编号：1. 2. 3.（独立行，短文本）
        4. 常见标题关键词

        Args:
            text: 段落文本

        Returns:
            是否为标题
        """
        import re

        if not text or len(text) > 100:
            return False

        # 第一章、第二章、第三章
        if re.match(r'^第[一二三四五六七八九十百]+[章节条款部分]', text):
            return True

        # 一、二、三、（中文数字编号）
        if re.match(r'^[一二三四五六七八九十]+、', text):
            return True

        # （一）、（二）、（三）
        if re.match(r'^（[一二三四五六七八九十]+）', text):
            return True

        # 1. 2. 3.（阿拉伯数字编号，短文本）
        # 注意：避免误判列表项，只匹配短标题
        if re.match(r'^\d+\.\s+\S', text) and len(text) <= 50:
            # 排除明显的列表项（以分号、句号结尾）
            if not re.search(r'[；。；]$', text):
                return True

        # 常见标题关键词（必须出现在行首）
        heading_keywords = [
            '目录', '前言', '附录', '参考文献', '致谢',
            '摘要', '关键词', 'Abstract', 'Keywords',
        ]
        for keyword in heading_keywords:
            if text.startswith(keyword) and len(text) <= 20:
                return True

        return False

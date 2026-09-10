# backend/app/core/parser/markdown_parser.py
"""Markdown 解析器实现"""

import logging
from typing import List
import re

from .base import (
    BaseParser,
    ParsedDocument,
    DocumentElement,
    ElementPosition,
)

logger = logging.getLogger(__name__)


class MarkdownParser(BaseParser):
    """Markdown 文档解析器

    支持解析标准 Markdown，包括：
    - 标题层级
    - 段落
    - 列表
    - 代码块
    """

    async def parse(self, file_data: bytes, doc_id: str) -> ParsedDocument:
        """
        解析 Markdown 文档

        Args:
            file_data: Markdown 文件二进制数据
            doc_id: 文档 ID

        Returns:
            ParsedDocument: 解析结果
        """
        logger.info(f"Starting Markdown parsing: doc_id={doc_id}")

        # 1. 解码文本
        content = file_data.decode('utf-8')
        lines = content.split('\n')

        # 2. 提取元素
        elements: List[DocumentElement] = []
        elem_idx = 0

        in_code_block = False
        current_element = None

        for line in lines:
            # 代码块处理
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                if in_code_block:
                    # 开始代码块
                    current_element = DocumentElement(
                        element_id=f'{doc_id}-elem-{elem_idx}',
                        element_type='code',
                        content='',
                        position=ElementPosition(),
                        metadata={'language': line.strip()[3:]}
                    )
                else:
                    # 结束代码块
                    if current_element:
                        elements.append(current_element)
                        elem_idx += 1
                        current_element = None
                continue

            if in_code_block and current_element:
                current_element.content += line + '\n'
                continue

            # 标题处理
            if line.strip().startswith('#'):
                match = re.match(r'^(#+)\s+(.+)$', line)
                if match:
                    level = len(match.group(1))
                    element = DocumentElement(
                        element_id=f'{doc_id}-elem-{elem_idx}',
                        element_type='heading',
                        content=match.group(2),
                        position=ElementPosition(),
                        metadata={'level': level}
                    )
                    elements.append(element)
                    elem_idx += 1
                continue

            # 列表处理
            if re.match(r'^\s*[-*+]\s+', line) or re.match(r'^\s*\d+\.\s+', line):
                element = DocumentElement(
                    element_id=f'{doc_id}-elem-{elem_idx}',
                    element_type='list',
                    content=line.strip(),
                    position=ElementPosition(),
                    metadata={'is_ordered': bool(re.match(r'^\s*\d+\.', line))}
                )
                elements.append(element)
                elem_idx += 1
                continue

            # 段落处理
            if line.strip():
                element = DocumentElement(
                    element_id=f'{doc_id}-elem-{elem_idx}',
                    element_type='paragraph',
                    content=line.strip(),
                    position=ElementPosition(),
                    metadata={}
                )
                elements.append(element)
                elem_idx += 1

        # 3. 元数据
        metadata = self._extract_metadata(file_data)
        metadata.update({
            'line_count': len(lines),
            'element_count': len(elements),
        })

        logger.info(f"Markdown parsing completed: doc_id={doc_id}, elements={len(elements)}")

        return ParsedDocument(
            doc_id=doc_id,
            file_key='',
            elements=elements,
            metadata=metadata,
            structure=None,
        )
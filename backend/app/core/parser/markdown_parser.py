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
        in_table = False  # 新增：表格状态标志
        current_element = None
        current_paragraph_lines = []  # 收集连续的段落行
        table_lines = []  # 新增：收集表格行

        def flush_paragraph():
            """将累积的段落行合并为一个元素"""
            nonlocal elem_idx
            if current_paragraph_lines:
                paragraph_content = '\n'.join(current_paragraph_lines)
                element = DocumentElement(
                    element_id=f'{doc_id}-elem-{elem_idx}',
                    element_type='paragraph',
                    content=paragraph_content,
                    position=ElementPosition(),
                    metadata={}
                )
                elements.append(element)
                elem_idx += 1
                current_paragraph_lines.clear()

        def flush_table():
            """将累积的表格行合并为一个表格元素"""
            nonlocal elem_idx
            if table_lines:
                table_content = '\n'.join(table_lines)
                # 统计数据行数
                # 表格结构：表头行 + 分隔符行 + 数据行
                # 只统计数据行（排除表头和分隔符）
                separator_pattern = re.compile(r'^\s*\|[\s\-:|]+\|')
                # 第一行是表头，第二行是分隔符，之后是数据行
                data_rows = len([line for i, line in enumerate(table_lines)
                               if line.strip()
                               and i > 1  # 跳过表头（i=0）和分隔符（i=1）
                               and not separator_pattern.match(line)])
                element = DocumentElement(
                    element_id=f'{doc_id}-elem-{elem_idx}',
                    element_type='table',
                    content=table_content,
                    position=ElementPosition(),
                    metadata={'rows': data_rows, 'total_lines': len(table_lines)}
                )
                elements.append(element)
                elem_idx += 1
                table_lines.clear()

        for line in lines:
            # 代码块处理
            if line.strip().startswith('```'):
                flush_paragraph()  # 结束当前段落
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

            # 表格处理（新增）
            if line.strip().startswith('|'):
                flush_paragraph()  # 结束当前段落
                if not in_table:
                    # 开始新的表格
                    in_table = True
                    table_lines = [line]
                else:
                    # 继续收集表格行
                    table_lines.append(line)
                continue
            elif in_table:
                # 表格结束（遇到非表格行）
                flush_table()
                in_table = False

            # 标题处理
            if line.strip().startswith('#'):
                flush_paragraph()  # 结束当前段落
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
                flush_paragraph()  # 结束当前段落
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
                # 累积连续的段落行
                current_paragraph_lines.append(line.strip())
            else:
                # 空行，结束当前段落
                flush_paragraph()

        # 处理文档末尾可能剩余的段落
        flush_paragraph()

        # 处理文档末尾可能剩余的表格
        if in_table:
            flush_table()

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
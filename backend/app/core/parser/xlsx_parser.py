"""XLSX 解析器实现"""

import logging
from typing import List
from openpyxl import load_workbook
import io

from .base import (
    BaseParser,
    ParsedDocument,
    DocumentElement,
    ElementPosition,
)

logger = logging.getLogger(__name__)


class XLSXParser(BaseParser):
    """XLSX 文档解析器

    使用 openpyxl 提取内容，支持：
    - 工作表遍历
    - 单元格内容提取
    """

    async def parse(self, file_data: bytes, doc_id: str) -> ParsedDocument:
        """
        解析 XLSX 文档

        Args:
            file_data: XLSX 文件二进制数据
            doc_id: 文档 ID

        Returns:
            ParsedDocument: 解析结果
        """
        logger.info(f"Starting XLSX parsing: doc_id={doc_id}")

        # 1. 打开工作簿
        wb = load_workbook(io.BytesIO(file_data), read_only=True)

        # 2. 提取元素
        elements: List[DocumentElement] = []
        elem_idx = 0

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]

            # 将每个工作表作为一个表格元素
            table_content = self._extract_sheet_content(ws, sheet_name)

            if table_content:
                element = DocumentElement(
                    element_id=f'{doc_id}-elem-{elem_idx}',
                    element_type='table',
                    content=table_content,
                    position=ElementPosition(),
                    metadata={
                        'sheet_name': sheet_name,
                        'row_count': ws.max_row,
                        'column_count': ws.max_column,
                    }
                )
                elements.append(element)
                elem_idx += 1

        # 3. 提取元数据
        metadata = self._extract_metadata(file_data)
        metadata.update({
            'sheet_count': len(wb.sheetnames),
            'sheet_names': wb.sheetnames,
        })

        logger.info(f"XLSX parsing completed: doc_id={doc_id}, elements={len(elements)}")

        return ParsedDocument(
            doc_id=doc_id,
            file_key='',
            elements=elements,
            metadata=metadata,
            structure=None,
        )

    def _extract_sheet_content(self, ws, sheet_name: str) -> str:
        """提取工作表内容"""
        rows = []

        for row in ws.iter_rows(values_only=True):
            # 过滤空行
            if any(cell is not None for cell in row):
                row_str = ' | '.join(str(cell) if cell is not None else '' for cell in row)
                rows.append(row_str)

        if rows:
            return f"Sheet: {sheet_name}\n" + '\n'.join(rows)

        return ''

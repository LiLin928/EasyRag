"""文档解析调度器"""

import logging
from typing import Dict, Type

from .base import BaseParser, ParsedDocument
from .pdf_parser import PDFParser
from .docx_parser import DOCXParser
from .xlsx_parser import XLSXParser
from .markdown_parser import MarkdownParser

logger = logging.getLogger(__name__)


class DocumentDispatcher:
    """文档解析调度器

    职责：
    - 识别文件类型
    - 选择合适的解析器
    - 处理解析错误
    """

    PARSER_MAP: Dict[str, Type[BaseParser]] = {
        'pdf': PDFParser,
        'docx': DOCXParser,
        'doc': DOCXParser,  # 转换为 docx
        'xlsx': XLSXParser,
        'xls': XLSXParser,
        'md': MarkdownParser,
        'markdown': MarkdownParser,
        'txt': MarkdownParser,  # 当作简单文本
    }

    def __init__(self):
        self._parsers: Dict[str, BaseParser] = {}

    def _get_parser_for_extension(self, ext: str) -> BaseParser:
        """获取指定扩展名的解析器"""
        if ext not in self._parsers:
            parser_class = self.PARSER_MAP.get(ext)
            if not parser_class:
                raise ValueError(f"Unsupported file type: {ext}")
            self._parsers[ext] = parser_class()

        return self._parsers[ext]

    async def _dispatch_from_data(
        self,
        file_data: bytes,
        filename: str,
        doc_id: str
    ) -> ParsedDocument:
        """
        从文件数据调度解析

        Args:
            file_data: 文件二进制数据
            filename: 文件名（用于提取扩展名）
            doc_id: 文档 ID

        Returns:
            ParsedDocument: 解析结果
        """
        logger.info(f"Dispatching parse: filename={filename}, doc_id={doc_id}")

        # 1. 提取扩展名
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        # 2. 获取解析器
        parser = self._get_parser_for_extension(ext)

        # 3. 执行解析
        try:
            result = await parser.parse(file_data, doc_id)
            result.file_key = filename

            logger.info(
                f"Parse completed: doc_id={doc_id}, "
                f"elements={len(result.elements)}, "
                f"parser={parser.__class__.__name__}"
            )

            return result

        except Exception as e:
            logger.error(f"Parse failed: doc_id={doc_id}, error={e}")
            raise


# 保留旧的函数接口以保持向后兼容
async def parse(ext: str, path: str):
    """旧的函数接口（向后兼容）"""
    dispatcher = DocumentDispatcher()
    # 注意：这个旧接口需要文件路径，而新的使用文件数据
    # 保留它只是为了不破坏现有代码
    raise NotImplementedError("Use DocumentDispatcher._dispatch_from_data instead")

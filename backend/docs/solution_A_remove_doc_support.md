"""
解决方案 A: 移除 .doc 文件支持（推荐临时方案）

适用场景：
- 快速修复，避免用户混淆
- 后续再添加完整的 .doc 支持

修改内容：
1. dispatcher.py - 移除 'doc' 映射
2. 上传接口 - 明确提示不支持 .doc
3. 错误处理 - 友好的错误消息
"""

# ===== 修改 1: dispatcher.py =====
# 文件：backend/app/core/parser/dispatcher.py

# 修改前（第 24-33 行）：
PARSER_MAP: Dict[str, Type[BaseParser]] = {
    'pdf': PDFParser,
    'docx': DOCXParser,
    'doc': DOCXParser,  # ❌ 移除这一行
    'xlsx': XLSXParser,
    'xls': XLSXParser,
    'md': MarkdownParser,
    'markdown': MarkdownParser,
    'txt': MarkdownParser,
}

# 修改后：
PARSER_MAP: Dict[str, Type[BaseParser]] = {
    'pdf': PDFParser,
    'docx': DOCXParser,
    # 移除 'doc' - 明确不支持 Word 97-2003 格式
    'xlsx': XLSXParser,
    'xls': XLSXParser,
    'md': MarkdownParser,
    'markdown': MarkdownParser,
    'txt': MarkdownParser,
}


# ===== 修改 2: 错误处理 =====
# 文件：backend/app/core/parser/dispatcher.py
# 方法：_get_parser_for_extension

# 修改前（第 38-46 行）：
def _get_parser_for_extension(self, ext: str) -> BaseParser:
    """获取指定扩展名的解析器"""
    if ext not in self._parsers:
        parser_class = self.PARSER_MAP.get(ext)
        if not parser_class:
            raise ValueError(f"Unsupported file type: {ext}")
        self._parsers[ext] = parser_class()

    return self._parsers[ext]

# 修改后：添加友好的错误消息
def _get_parser_for_extension(self, ext: str) -> BaseParser:
    """获取指定扩展名的解析器"""
    if ext not in self._parsers:
        parser_class = self.PARSER_MAP.get(ext)
        if not parser_class:
            # 特殊提示 .doc 文件
            if ext == 'doc':
                raise ValueError(
                    "不支持 Word 97-2003 格式（.doc），"
                    "请转换为 .docx 格式后再上传"
                )
            raise ValueError(f"Unsupported file type: {ext}")
        self._parsers[ext] = parser_class()

    return self._parsers[ext]


# ===== 修改 3: 上传接口提示 =====
# 文件：backend/app/api/v2/documents.py
# 方法：upload_document

# 在上传接口的文档字符串或响应中添加提示：
"""
支持的文件格式：
- PDF (.pdf)
- Word 2007+ (.docx) ← 明确说明
- Excel (.xlsx, .xls)
- Markdown (.md, .markdown)
- 纯文本 (.txt)

不支持：Word 97-2003 (.doc)
"""
"""解析器分发，按扩展名选择解析器。"""
from app.core.parser import docx_parser, md_parser, pdf_parser, xlsx_parser
from app.core.parser.models import ParsedElement
from app.exceptions import BizException, ErrorCode


async def parse(ext: str, path: str) -> list[ParsedElement]:
    """按扩展名分发到对应解析器；不支持则抛 UNSUPPORTED_FILE。

    Args:
        ext: 文件扩展名（带或不带点）。
        path: 文件本地路径。

    Returns:
        解析出的 ParsedElement 列表。
    """
    e = ext.lower().lstrip(".")
    if e == "pdf":
        return await pdf_parser.parse(path)
    if e == "docx":
        return await docx_parser.parse(path)
    if e in ("xlsx", "xls"):
        return await xlsx_parser.parse(path)
    if e in ("md", "txt", "markdown"):
        return await md_parser.parse(path)
    raise BizException(ErrorCode.UNSUPPORTED_FILE, f"不支持的文件格式: {ext}")

"""PDF 解析器（PyMuPDF 文本块 + pdfplumber 表格）。"""
import fitz  # pymupdf
import pdfplumber

from app.core.parser.models import ParsedElement


async def parse(path: str) -> list[ParsedElement]:
    """解析 pdf：按页提取文本块（保留顺序）+ 表格（HTML）。"""
    elements: list[ParsedElement] = []
    doc = fitz.open(path)
    table_pages = _extract_tables(path)
    for page in doc:
        pno = page.number + 1
        for block in page.get_text("blocks"):
            text = (block[4] or "").strip()
            if text:
                elements.append(ParsedElement("text", text, pno))
        for html in table_pages.get(pno, []):
            elements.append(ParsedElement("table", html, pno))
    doc.close()
    return elements


def _extract_tables(path: str) -> dict[int, list[str]]:
    """用 pdfplumber 提取每页表格，转 HTML。"""
    out: dict[int, list[str]] = {}
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            for t in page.extract_tables() or []:
                out.setdefault(i + 1, []).append(_table_to_html(t))
    return out


def _table_to_html(rows: list) -> str:
    """二维列表转 HTML 表格字符串。"""
    body = "".join("<tr>" + "".join(f"<td>{(c or '')}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table>{body}</table>"

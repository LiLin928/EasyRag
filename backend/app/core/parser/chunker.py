"""结构化分块：按 heading 分节，节内按 chunk_size 滑窗切分。"""
from app.core.parser.models import ParsedElement


def chunk(elements: list[ParsedElement], chunk_size: int = 512, overlap: int = 64) -> list[dict]:
    """按 heading 分节，节内按 chunk_size 滑窗切分（overlap）。返回 chunk dict 列表。

    每个 chunk dict 含：content / content_search / page_number / section_path /
    clause_title（当前节标题）/ seq（块序号）。
    """
    result: list[dict] = []
    section_stack: list[tuple[int, str]] = []  # (level, title)
    buf = ""
    buf_page = 1
    seq = 0

    def section_path() -> str:
        return " > ".join(t for _, t in section_stack)

    def flush():
        nonlocal buf, seq
        text = buf.strip()
        if not text:
            buf = ""
            return
        i = 0
        step = max(1, chunk_size - overlap)
        while i < len(text):
            piece = text[i:i + chunk_size]
            result.append({
                "content": piece,
                "content_search": piece,
                "page_number": buf_page,
                "section_path": section_path(),
                "clause_title": section_stack[-1][1] if section_stack else None,
                "seq": seq,
            })
            seq += 1
            if i + chunk_size >= len(text):
                break
            i += step
        buf = ""

    for e in elements:
        if e.element_type == "heading" and e.level > 0:
            flush()
            # 弹出同级及更深的标题
            while section_stack and section_stack[-1][0] >= e.level:
                section_stack.pop()
            section_stack.append((e.level, e.content))
        else:
            if not buf:
                buf_page = e.page_number
            buf += ("\n" if buf else "") + e.content
            if len(buf) >= chunk_size:
                flush()
    flush()
    return result

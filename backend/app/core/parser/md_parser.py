"""Markdown/TXT 解析器。"""
import re

from app.core.parser.models import ParsedElement

_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")


async def parse(path: str) -> list[ParsedElement]:
    """逐行解析 md/txt：# 开头为 heading（level=井号数），其余为 text。"""
    elements: list[ParsedElement] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            m = _HEADING.match(line)
            if m:
                elements.append(ParsedElement("heading", m.group(2).strip(), 1, level=len(m.group(1))))
            else:
                elements.append(ParsedElement("text", line, 1))
    return elements

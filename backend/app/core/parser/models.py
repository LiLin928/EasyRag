"""解析元素数据模型。"""
from dataclasses import dataclass


@dataclass
class ParsedElement:
    """解析后的元素（文本/表格/图片/标题）。

    Attributes:
        element_type: text/table/image/heading。
        content: 文本内容/表格 HTML/标题。
        page_number: 页码。
        section_path: 章节路径（TreeBuilder/Chunker 填充）。
        image_key: 图片存储键（可空）。
        level: heading 层级（1-6）；非 heading 为 0。
    """

    element_type: str
    content: str
    page_number: int
    section_path: str = ""
    image_key: str | None = None
    level: int = 0

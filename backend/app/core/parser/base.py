# backend/app/core/parser/base.py
"""解析器基类和核心数据结构"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from datetime import datetime


@dataclass
class ElementPosition:
    """元素位置信息"""
    page: int = 0
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass
class DocumentElement:
    """文档元素"""
    element_id: str
    element_type: str  # 'paragraph', 'heading', 'table', 'image', 'list'
    content: str
    position: ElementPosition
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TreeNode:
    """树节点"""
    node_id: str
    level: int
    title: str
    element_ids: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)


@dataclass
class DocumentTree:
    """文档树结构"""
    root: TreeNode
    nodes: List[TreeNode]


@dataclass
class ParsedDocument:
    """解析后的文档"""
    doc_id: str
    file_key: str
    elements: List[DocumentElement]
    metadata: Dict[str, Any] = field(default_factory=dict)
    structure: Optional[DocumentTree] = None

    @property
    def element_count(self) -> int:
        """元素数量"""
        return len(self.elements)


class BaseParser(ABC):
    """解析器基类"""

    @abstractmethod
    async def parse(self, file_data: bytes, doc_id: str) -> ParsedDocument:
        """
        解析文档

        Args:
            file_data: 文件二进制数据
            doc_id: 文档 ID

        Returns:
            ParsedDocument: 解析结果
        """
        pass

    def _extract_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """提取文档元数据"""
        return {
            'file_size': len(file_data),
            'parse_time': datetime.utcnow().isoformat(),
        }
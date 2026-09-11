"""文档树构建器"""

import logging
import re
from typing import List
import uuid

from .base import DocumentElement, DocumentTree, TreeNode as TreeNodeData

logger = logging.getLogger(__name__)


class TreeBuilder:
    """文档树构建器

    职责：
    - 分析文档结构
    - 识别标题层级
    - 构建导航树
    """

    HEADING_PATTERNS = [
        r'^#+\s+',  # Markdown 标题
        r'^第[一二三四五六七八九十]+[章节篇]',  # 中文章节
        r'^\d+\.\d*\s+',  # 数字编号
    ]

    async def build(
        self,
        elements: List[DocumentElement],
        doc_id: str
    ) -> DocumentTree:
        """
        构建文档树

        Args:
            elements: 文档元素列表
            doc_id: 文档 ID

        Returns:
            DocumentTree: 文档树结构
        """
        logger.info(f"Building document tree: doc_id={doc_id}, elements={len(elements)}")

        # 1. 识别标题节点
        heading_nodes = []
        for elem in elements:
            if self._is_heading(elem):
                node = self._create_node(elem, doc_id)
                heading_nodes.append(node)

        if not heading_nodes:
            # 没有标题，创建一个根节点
            root = TreeNodeData(
                node_id=str(uuid.uuid4()),
                level=0,
                title='Root',
                element_ids=[],
                children=[]
            )
            # 将所有元素分配给根节点
            self._assign_elements_to_nodes(elements, [root])
            return DocumentTree(root=root, nodes=[root])

        # 2. 构建层级关系
        root = TreeNodeData(
            node_id='root',
            level=0,
            title='Root',
            element_ids=[],
            children=[]
        )

        # 使用栈来维护当前路径
        stack = [root]

        for node in heading_nodes:
            # 找到合适的父节点
            while len(stack) > 1 and stack[-1].level >= node.level:
                stack.pop()

            # 添加为子节点
            parent = stack[-1]
            parent.children.append(node.node_id)

            # 压入栈
            stack.append(node)

        # 3. 分配元素到节点
        self._assign_elements_to_nodes(elements, heading_nodes)

        logger.info(f"Tree built: nodes={len(heading_nodes)}, depth={len(stack)}")

        return DocumentTree(root=root, nodes=heading_nodes)

    def _is_heading(self, elem: DocumentElement) -> bool:
        """判断元素是否为标题"""
        # 类型判断
        if elem.element_type == 'heading':
            return True

        # 内容模式匹配
        content = elem.content.strip()
        for pattern in self.HEADING_PATTERNS:
            if re.match(pattern, content):
                return True

        return False

    def _create_node(self, elem: DocumentElement, doc_id: str) -> TreeNodeData:
        """创建树节点"""
        level = elem.metadata.get('level', 1)

        return TreeNodeData(
            node_id=f'{doc_id}-node-{elem.element_id}',
            level=level,
            title=elem.content,
            element_ids=[elem.element_id],
            children=[]
        )

    def _assign_elements_to_nodes(
        self,
        elements: List[DocumentElement],
        nodes: List[TreeNodeData]
    ):
        """分配元素到节点

        每个标题节点包含从它开始到下一个标题之间的所有元素。
        如果没有标题节点，所有元素分配给传入的节点（通常是根节点）。
        """
        if not nodes or not elements:
            return

        # 找出所有标题元素的索引
        heading_indices = []
        for idx, elem in enumerate(elements):
            if self._is_heading(elem):
                heading_indices.append(idx)

        # 如果没有标题，将所有元素分配给第一个节点（通常是根节点）
        if not heading_indices:
            for elem in elements:
                if elem.element_id not in nodes[0].element_ids:
                    nodes[0].element_ids.append(elem.element_id)
            return

        # 为每个标题节点分配元素
        for node_idx, node in enumerate(nodes):
            # 当前标题的元素索引
            current_heading_idx = heading_indices[node_idx] if node_idx < len(heading_indices) else len(elements)

            # 下一个标题的元素索引（如果没有下一个标题，则到末尾）
            next_heading_idx = heading_indices[node_idx + 1] if node_idx + 1 < len(heading_indices) else len(elements)

            # 将当前标题到下一个标题之间的所有元素分配给当前节点
            for elem_idx in range(current_heading_idx, next_heading_idx):
                elem = elements[elem_idx]
                if elem.element_id not in node.element_ids:
                    node.element_ids.append(elem.element_id)


# 保留旧的函数接口以保持向后兼容
async def build_tree(doc_id: str, elements: list):
    """旧的函数接口（向后兼容）"""
    builder = TreeBuilder()
    # 注意：这个旧接口使用 ParsedElement，而新的使用 DocumentElement
    # 保留它只是为了不破坏现有代码
    raise NotImplementedError("Use TreeBuilder.build instead")

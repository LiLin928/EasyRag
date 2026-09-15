"""父子分块器

将树节点（章节）作为父分段，章节内容切分为子分段。
"""
import logging
from typing import List

from app.core.parser.base import DocumentElement

logger = logging.getLogger(__name__)


class ParentChildChunker:
    """父子分块器

    将树节点（章节）作为父分段，章节内容切分为子分段。

    核心思想：
    - 短章节（< threshold）：单个子分段
    - 长章节（> threshold）：按长度切分为多个子分段

    Args:
        child_chunk_size: 子分段目标大小（字符数）
        child_chunk_overlap: 子分段重叠字符数
        min_child_chunk_size: 最小子分段大小
    """

    def __init__(
        self,
        child_chunk_size: int = 200,
        child_chunk_overlap: int = 50,
        min_child_chunk_size: int = 100
    ):
        self.child_chunk_size = child_chunk_size
        self.child_chunk_overlap = child_chunk_overlap
        self.min_child_chunk_size = min_child_chunk_size

    async def chunk(
        self,
        tree_nodes: List[dict],
        elements: List[DocumentElement],
        doc_id: str,
        kb_id: str
    ) -> List[dict]:
        """
        生成父子分段

        Args:
            tree_nodes: 树节点列表（来自 TreeBuilder.build 返回的 nodes）
            elements: 元素列表
            doc_id: 文档 ID
            kb_id: 知识库 ID

        Returns:
            子分段列表（字典格式）
        """
        logger.info(
            f"Parent-child chunking: doc_id={doc_id}, "
            f"tree_nodes={len(tree_nodes)}, elements={len(elements)}"
        )

        child_chunks = []

        for node in tree_nodes:
            # 1. 获取该节点的所有元素
            node_elements = self._get_elements_by_node(node, elements)

            if not node_elements:
                continue

            # 2. 生成父分段内容（所有元素拼接）
            parent_content = '\n\n'.join(
                elem.content for elem in node_elements if elem.content
            )

            if not parent_content.strip():
                continue

            # 3. 判断是否需要切分
            if len(parent_content) <= self.child_chunk_size:
                # 短章节：单个子分段
                child_chunks.append({
                    'doc_id': doc_id,
                    'kb_id': kb_id,
                    'tree_node_id': node['node_id'],
                    'position': 1,
                    'content': parent_content,
                    'char_count': len(parent_content),
                    'metadata': {
                        'parent_title': node['title'],
                        'parent_level': node['level'],
                    }
                })
            else:
                # 长章节：切分为多个子分段
                sub_chunks = self._split_parent_content(
                    parent_content
                )

                for i, sub_content in enumerate(sub_chunks, start=1):
                    child_chunks.append({
                        'doc_id': doc_id,
                        'kb_id': kb_id,
                        'tree_node_id': node['node_id'],
                        'position': i,
                        'content': sub_content,
                        'char_count': len(sub_content),
                        'metadata': {
                            'parent_title': node['title'],
                            'parent_level': node['level'],
                        }
                    })

        logger.info(f"Generated {len(child_chunks)} child chunks")
        return child_chunks

    def _get_elements_by_node(
        self,
        node: dict,
        elements: List[DocumentElement]
    ) -> List[DocumentElement]:
        """
        获取树节点的所有元素

        Args:
            node: 树节点（包含 node_id 和 element_ids）
            elements: 所有元素列表

        Returns:
            该节点包含的元素列表
        """
        # 从 node.element_ids 中获取元素
        element_ids = set(node.get('element_ids', []))

        return [
            elem for elem in elements
            if elem.element_id in element_ids
        ]

    def _split_parent_content(
        self,
        content: str
    ) -> List[str]:
        """
        切分父分段内容

        优先按句子边界切分，保持语义完整性。

        Args:
            content: 父分段内容

        Returns:
            子分段内容列表
        """
        chunks = []
        start = 0
        text_len = len(content)

        while start < text_len:
            # 计算切分点
            end = min(start + self.child_chunk_size, text_len)

            # 寻找句子边界（优先在句号、问号、感叹号处切分）
            if end < text_len:
                # 向后找句子结束符（最多向后看 50 个字符）
                search_end = min(end + 50, text_len)
                best_sep = -1

                for sep in ['。', '！', '？', '；', '\n\n', '\n']:
                    last_sep = content.rfind(sep, start, search_end)
                    if last_sep > start + self.min_child_chunk_size:
                        best_sep = max(best_sep, last_sep)

                if best_sep > start:
                    end = best_sep + 1

            chunk = content[start:end].strip()
            if len(chunk) >= self.min_child_chunk_size:
                chunks.append(chunk)

            # 移动到下一个位置
            # 如果已经到末尾，退出循环
            if end >= text_len:
                break

            # 考虑重叠，但至少前进最小字符数
            next_start = end - self.child_chunk_overlap
            if next_start <= start + self.min_child_chunk_size:
                next_start = end

            start = next_start

        return chunks
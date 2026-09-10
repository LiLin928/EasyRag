"""文档分块器"""

import logging
from typing import List

from .base import DocumentElement

logger = logging.getLogger(__name__)


class Chunker:
    """文档分块器

    职责：
    - 语义分块
    - 控制块大小
    - 保留上下文
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100
    ):
        """
        初始化分块器

        Args:
            chunk_size: 目标块大小（字符数）
            chunk_overlap: 重叠字符数
            min_chunk_size: 最小块大小
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    async def chunk(
        self,
        elements: List[DocumentElement],
        doc_id: str,
        kb_id: str = None
    ) -> List[dict]:
        """
        分块处理

        Args:
            elements: 文档元素列表
            doc_id: 文档 ID
            kb_id: 知识库 ID（可选）

        Returns:
            List[dict]: 分块列表（简化为字典，实际应返回 Chunk 模型）
        """
        logger.info(f"Chunking document: doc_id={doc_id}, elements={len(elements)}")

        chunks: List[dict] = []
        current_elements: List[DocumentElement] = []
        current_size = 0
        chunk_idx = 0

        for elem in elements:
            # 只处理文本类型
            if elem.element_type not in ['paragraph', 'heading', 'list']:
                continue

            text = elem.content
            text_size = len(text)

            # 检查是否需要新块
            if current_size + text_size > self.chunk_size and current_size >= self.min_chunk_size:
                # 保存当前块
                chunk = self._create_chunk_dict(
                    current_elements,
                    doc_id,
                    kb_id,
                    chunk_idx
                )
                chunks.append(chunk)
                chunk_idx += 1

                # 重叠处理
                overlap_elements = self._get_overlap(current_elements)
                current_elements = overlap_elements
                current_size = sum(len(e.content) for e in overlap_elements)

            current_elements.append(elem)
            current_size += text_size

        # 保存最后一块
        if current_elements and current_size >= self.min_chunk_size:
            chunk = self._create_chunk_dict(
                current_elements,
                doc_id,
                kb_id,
                chunk_idx
            )
            chunks.append(chunk)

        logger.info(f"Chunking completed: chunks={len(chunks)}")

        return chunks

    def _create_chunk_dict(
        self,
        elements: List[DocumentElement],
        doc_id: str,
        kb_id: str,
        chunk_idx: int
    ) -> dict:
        """创建 Chunk 字典（简化版）"""
        content = '\n\n'.join(elem.content for elem in elements)

        return {
            'doc_id': doc_id,
            'kb_id': kb_id,
            'content': content,
            'chunk_index': chunk_idx,
            'metadata': {
                'element_ids': [elem.element_id for elem in elements],
                'element_types': [elem.element_type for elem in elements],
                'chunk_index': chunk_idx,
            },
        }

    def _get_overlap(
        self,
        elements: List[DocumentElement]
    ) -> List[DocumentElement]:
        """获取重叠元素"""
        if not elements:
            return []

        # 从后往前取，直到达到重叠大小
        overlap = []
        size = 0

        for elem in reversed(elements):
            if size + len(elem.content) > self.chunk_overlap:
                break
            overlap.insert(0, elem)
            size += len(elem.content)

        return overlap


# 保留旧的函数接口以保持向后兼容
def chunk(elements: list, chunk_size: int = 512, overlap: int = 64) -> list[dict]:
    """旧的函数接口（向后兼容）"""
    # 注意：这个旧接口使用 ParsedElement，而新的使用 DocumentElement
    # 保留它只是为了不破坏现有代码
    raise NotImplementedError("Use Chunker.chunk instead")

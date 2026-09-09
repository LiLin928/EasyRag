"""导航式检索。

基于文档树结构，智能识别查询范围，提高检索精度。
"""
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from app.models.tree_node import TreeNode, EMBEDDING_DIM
from app.models.chunk import Chunk
from app.core.retrieval.embedder import Embedder


class NavigationSearch:
    """导航式检索。

    通过分析 Top-K 结果所属的文档树节点，智能确定查询范围。
    """

    def __init__(
        self,
        confidence_threshold: float = 0.15,
        anchor_count: int = 3
    ):
        """初始化。

        Args:
            confidence_threshold: 置信度阈值（低于此值认为无法确定范围）
            anchor_count: 锚点数量（用于确定范围的节点数）
        """
        self.confidence_threshold = confidence_threshold
        self.anchor_count = anchor_count

    async def identify_scope(
        self,
        session: AsyncSession,
        kb_id: str,
        query: str,
        top_candidates: List[Dict],
        embedder: Optional[Embedder] = None
    ) -> Optional[Dict]:
        """识别查询范围。

        通过分析 Top-K 结果所属的文档树节点，智能确定查询范围。

        Args:
            session: 数据库会话
            kb_id: 知识库ID
            query: 查询文本
            top_candidates: Top-K 检索结果
            embedder: Embedder 实例（用于语义匹配节点）

        Returns:
            识别出的范围（包含节点ID和置信度），None表示无法确定
        """
        # 方法1：基于元数据中的 section_path 统计
        node_scores = {}

        for candidate in top_candidates[:self.anchor_count]:
            metadata = candidate.get("metadata", {})
            section_path = metadata.get("section_path")
            chunk_id = candidate.get("chunk_id")

            if not section_path:
                continue

            # 查找对应的树节点
            node = await session.scalar(
                select(TreeNode).join(
                    Chunk, TreeNode.document_id == Chunk.document_id
                ).where(
                    and_(
                        Chunk.id == chunk_id,
                        TreeNode.title == section_path.split("/")[-1]
                    )
                )
            )

            if not node:
                continue

            # 累加分数
            if str(node.id) not in node_scores:
                node_scores[str(node.id)] = {
                    "node": node,
                    "score": 0
                }
            node_scores[str(node.id)]["score"] += candidate.get("final_score", 1)

        if not node_scores:
            return None

        # 找出得分最高的节点
        best_node_entry = max(node_scores.values(), key=lambda x: x["score"])
        total_score = sum(entry["score"] for entry in node_scores.values())

        confidence = best_node_entry["score"] / total_score if total_score > 0 else 0

        # 置信度过低则不限定范围
        if confidence < self.confidence_threshold:
            return None

        best_node = best_node_entry["node"]

        return {
            "node_id": str(best_node.id),
            "node_title": best_node.title,
            "confidence": confidence,
            "filter_condition": {
                "section_path": f"{best_node.title}"
            }
        }

    async def apply_navigation_filter(
        self,
        session: AsyncSession,
        kb_id: str,
        candidates: List[Dict],
        scope: Optional[Dict]
    ) -> List[Dict]:
        """应用导航范围过滤。

        Args:
            session: 数据库会话
            kb_id: 知识库ID
            candidates: 候选结果
            scope: 识别出的范围

        Returns:
            过滤后的结果
        """
        if not scope:
            # 无范围限定，直接返回
            return candidates

        # 过滤出属于该范围的文档
        filter_condition = scope.get("filter_condition", {})
        filtered = []

        for candidate in candidates:
            metadata = candidate.get("metadata", {})
            # 检查是否属于该范围
            match = True
            for key, value in filter_condition.items():
                if metadata.get(key) != value:
                    match = False
                    break

            if match:
                candidate["navigation_scoped"] = True
                candidate["navigation_node"] = scope["node_title"]
                filtered.append(candidate)

        # 如果过滤后为空，返回原始结果
        return filtered if filtered else candidates

    async def semantic_node_match(
        self,
        session: AsyncSession,
        kb_id: str,
        query: str,
        embedder: Embedder
    ) -> Optional[Dict]:
        """语义匹配树节点。

        使用查询向量与树节点的导航向量进行相似度匹配。

        Args:
            session: 数据库会话
            kb_id: 知识库ID
            query: 查询文本
            embedder: Embedder 实例

        Returns:
            匹配的节点信息，None 表示无匹配
        """
        # 向量化查询
        query_vector = await embedder.embed_query(query)

        # 查询具有导航向量的树节点
        nodes = await session.scalars(
            select(TreeNode).where(
                TreeNode.nav_embedding.isnot(None)
            ).join(
                Chunk, TreeNode.document_id == Chunk.document_id
            ).where(
                Chunk.kb_id == kb_id
            )
        )

        nodes_list = nodes.all()

        if not nodes_list:
            return None

        # 计算相似度
        best_node = None
        best_score = 0

        for node in nodes_list:
            # 计算余弦相似度
            similarity = 1 - await session.scalar(
                select(TreeNode.nav_embedding.cosine_distance(query_vector)).where(
                    TreeNode.id == node.id
                )
            )

            if similarity > best_score:
                best_score = similarity
                best_node = node

        if best_node and best_score > 0.5:  # 相似度阈值
            return {
                "node_id": str(best_node.id),
                "node_title": best_node.title,
                "confidence": float(best_score),
                "filter_condition": {
                    "section_path": best_node.title
                }
            }

        return None
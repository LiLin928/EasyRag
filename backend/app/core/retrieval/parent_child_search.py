"""父子分段检索模块。

检索子分段，映射回父分段返回完整章节内容。

流程：
1. 向量检索子分段（child_chunks 表）
2. 通过 tree_node_id 映射回父分段（TreeNode）
3. 返回父分段的完整内容
"""
from typing import List, Dict
from sqlalchemy import text

from app.core.retrieval.metadata_filter import (
    MetadataFilter,
    build_predicates_for_kbs,
)
from app.db.session import async_session


_SQL_CHILD_CHUNKS = """
SELECT cc.id, cc.document_id, cc.tree_node_id, cc.kb_id,
       cc.position, cc.content, cc.metadata, cc.char_count,
       cc.embedding_model, d.name AS document_name,
       1 - (cc.embedding <=> cast(:emb as vector)) AS vector_score
FROM child_chunks cc
JOIN documents d ON d.id = cc.document_id
WHERE d.kb_id::text = ANY(cast(:kb_ids as text[]))
  AND d.enabled
  AND cc.enabled
  AND (cast(:doc_ids as uuid[]) IS NULL OR cc.document_id = ANY(cast(:doc_ids as uuid[])))
  AND (cast(:scope as uuid[]) IS NULL OR cc.id = ANY(cast(:scope as uuid[])))
  AND (cast(:embedding_model as text) IS NULL OR cc.embedding_model = cast(:embedding_model as text))
  AND (cast(:similarity_threshold as double precision) IS NULL
       OR 1 - (cc.embedding <=> cast(:emb as vector)) >= cast(:similarity_threshold as double precision))
  AND cc.embedding IS NOT NULL
"""

_ORDER_CHILD_CHUNKS = """
ORDER BY cc.embedding <=> cast(:emb as vector), cc.id
LIMIT :k
"""


def _hit_child(row) -> dict:
    """将子分段查询结果转换为字典"""
    return {
        "id": str(row["id"]),
        "document_id": str(row["document_id"]),
        "document_name": row["document_name"],
        "tree_node_id": str(row["tree_node_id"]),
        "position": row["position"],
        "content": row["content"],
        "metadata": row["metadata"] or {},
        "char_count": row["char_count"],
        "embedding_model": row["embedding_model"],
        "vector_score": float(row["vector_score"]),
    }


async def search_child_chunks(
    q_emb: list[float],
    kb_ids: list[str],
    doc_ids: list[str] | None,
    scope: list[str] | None,
    top_k: int,
    metadata_filter: MetadataFilter | None = None,
    embedding_model: str | None = None,
    similarity_threshold: float | None = None,
) -> list[dict]:
    """检索子分段

    Args:
        q_emb: 查询向量
        kb_ids: 知识库 ID 列表
        doc_ids: 文档 ID 列表（可选）
        scope: 子分段 ID 范围（可选）
        top_k: 返回数量
        metadata_filter: 元数据过滤器
        embedding_model: 向量模型名
        similarity_threshold: 相似度阈值

    Returns:
        子分段列表
    """
    async with async_session() as s:
        predicates, predicate_params = await build_predicates_for_kbs(
            s, kb_ids, metadata_filter
        )
        sql = _SQL_CHILD_CHUNKS
        if predicates:
            sql += " AND " + " AND ".join(predicates)
        sql += _ORDER_CHILD_CHUNKS
        rows = (
            await s.execute(
                text(sql),
                {
                    "emb": str(q_emb),
                    "kb_ids": kb_ids,
                    "doc_ids": doc_ids,
                    "scope": scope,
                    "k": top_k,
                    "embedding_model": embedding_model,
                    "similarity_threshold": similarity_threshold,
                    **predicate_params,
                },
            )
        ).mappings().all()
    return [_hit_child(row) for row in rows]


async def parent_child_search(
    q_emb: list[float],
    kb_ids: list[str],
    doc_ids: list[str] | None = None,
    scope: list[str] | None = None,
    top_k: int = 20,
    metadata_filter: MetadataFilter | None = None,
    embedding_model: str | None = None,
    similarity_threshold: float | None = None,
) -> List[Dict]:
    """父子分段检索

    检索子分段，映射回父分段返回。

    Args:
        q_emb: 查询向量
        kb_ids: 知识库 ID 列表
        doc_ids: 文档 ID 列表（可选）
        scope: 子分段 ID 范围（可选）
        top_k: 返回数量（父分段）
        metadata_filter: 元数据过滤器
        embedding_model: 向量模型名
        similarity_threshold: 相似度阈值

    Returns:
        父分段列表（包含完整章节内容和命中的子分段）
    """
    # 1. 向量检索子分段（检索更多，因为可能多个子分段属于同一个父分段）
    child_results = await search_child_chunks(
        q_emb=q_emb,
        kb_ids=kb_ids,
        doc_ids=doc_ids,
        scope=scope,
        top_k=top_k * 3,  # 检索更多子分段
        metadata_filter=metadata_filter,
        embedding_model=embedding_model,
        similarity_threshold=similarity_threshold,
    )

    if not child_results:
        return []

    # 2. 提取 tree_node_id 列表
    tree_node_ids = list(set(r['tree_node_id'] for r in child_results))

    # 3. 查询父分段（TreeNode）详情
    async with async_session() as session:
        # 查询树节点
        nodes_result = await session.execute(
            text("""
                SELECT id, document_id, title, level, parent_content,
                       parent_chunk_mode, child_chunk_count
                FROM doc_tree_nodes
                WHERE id = ANY(cast(:node_ids as uuid[]))
            """),
            {"node_ids": [str(nid) for nid in tree_node_ids]}
        )
        nodes_map = {
            str(row["id"]): row
            for row in nodes_result.mappings().all()
        }

    # 4. 按 tree_node_id 分组，合并评分
    parent_map = {}
    for child in child_results:
        node_id = child['tree_node_id']

        if node_id not in parent_map:
            # 获取父分段信息
            node_row = nodes_map.get(node_id)
            if not node_row:
                continue

            parent_map[node_id] = {
                'id': node_id,
                'document_id': str(node_row['document_id']),
                'document_name': child['document_name'],
                'title': node_row['title'],
                'level': node_row['level'],
                'content': node_row['parent_content'] or child['content'],  # 父分段完整内容
                'parent_chunk_mode': node_row['parent_chunk_mode'],
                'child_chunk_count': node_row['child_chunk_count'],
                'score': 0.0,
                'children': [],
                'section_path': node_row['title']
            }

        # 更新评分（取最高分）
        parent_map[node_id]['score'] = max(
            parent_map[node_id]['score'],
            child['vector_score']
        )

        # 添加命中的子分段
        parent_map[node_id]['children'].append({
            'id': child['id'],
            'position': child['position'],
            'content': child['content'],
            'score': child['vector_score']
        })

    # 5. 按评分排序，返回 top_k 个父分段
    results = sorted(
        parent_map.values(),
        key=lambda x: x['score'],
        reverse=True
    )[:top_k]

    return results
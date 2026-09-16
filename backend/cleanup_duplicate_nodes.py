"""清理重复的空父分段节点

问题：同一文档中存在多个重复的父分段，其中一些是空节点。

解决方案：
1. 删除 parent_content 为 NULL 且 child_chunk_count = 0 的节点
2. 删除没有子分段的节点
"""

import asyncio
import uuid
from sqlalchemy import text
from app.db.session import async_session


async def cleanup_duplicate_nodes():
    """清理重复的空节点"""

    async with async_session() as session:
        # 1. 查找所有空节点
        result = await session.execute(
            text('''
                SELECT id, title, document_id
                FROM doc_tree_nodes
                WHERE parent_content IS NULL
                AND child_chunk_count = 0
                AND id NOT IN (
                    SELECT DISTINCT tree_node_id FROM child_chunks
                )
            ''')
        )
        empty_nodes = result.mappings().all()

        print(f'找到 {len(empty_nodes)} 个空节点')

        if not empty_nodes:
            print('没有需要清理的节点')
            return

        # 2. 删除空节点
        for node in empty_nodes:
            print(f'删除空节点: {node["title"]} (ID: {node["id"]})')

            # 删除子节点的 parent_id 引用（如果有）
            await session.execute(
                text('UPDATE doc_tree_nodes SET parent_id = NULL WHERE parent_id = :id'),
                {'id': str(node['id'])}
            )

            # 删除节点
            await session.execute(
                text('DELETE FROM doc_tree_nodes WHERE id = :id'),
                {'id': str(node['id'])}
            )

        # 3. 提交事务
        await session.commit()
        print(f'\n成功清理 {len(empty_nodes)} 个空节点')


if __name__ == "__main__":
    asyncio.run(cleanup_duplicate_nodes())
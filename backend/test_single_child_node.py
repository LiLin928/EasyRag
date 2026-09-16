"""检查单子分段短章节的召回"""
import asyncio
from sqlalchemy import text
from app.db.session import async_session
from app.core.retrieval.parent_child_search import parent_child_search


async def test_single_child_chunk_node():
    """测试单子分段节点的召回"""

    # 找一个只有 1 个子分段的短章节
    async with async_session() as session:
        result = await session.execute(
            text('''
                SELECT id, title, parent_content, child_chunk_count,
                       LENGTH(parent_content) as content_len
                FROM doc_tree_nodes
                WHERE child_chunk_count = 1
                AND LENGTH(parent_content) < 100
                LIMIT 1
            ''')
        )
        node = result.mappings().first()

        if not node:
            print("没有找到单子分段短章节")
            return

        node_id = node['id']
        print(f"测试节点: {node['title']}")
        print(f"节点 ID: {node_id}")
        print(f"parent_content 长度: {node['content_len']}")
        print(f"parent_content: {node['parent_content']}")

        # 查询该节点的子分段
        child_result = await session.execute(
            text('''
                SELECT id, position, content, LENGTH(content) as len
                FROM child_chunks
                WHERE tree_node_id = :node_id
            '''),
            {'node_id': str(node_id)}
        )
        child = child_result.mappings().first()

        print(f"\n子分段 ID: {child['id']}")
        print(f"子分段内容长度: {child['len']}")
        print(f"子分段内容: {child['content']}")

        # 检查 embedding
        emb_result = await session.execute(
            text('SELECT embedding FROM child_chunks WHERE id = :id'),
            {'id': str(child['id'])}
        )
        emb_row = emb_result.first()
        if not emb_row or not emb_row[0]:
            print("子分段没有 embedding，跳过测试")
            return

        # 解析 embedding
        q_emb_str = emb_row[0]
        if isinstance(q_emb_str, str):
            q_emb_str = q_emb_str.strip('[]')
            q_emb = [float(x) for x in q_emb_str.split(',')]
        else:
            q_emb = list(q_emb_str)

        # 查询知识库 ID
        kb_result = await session.execute(
            text('SELECT DISTINCT kb_id FROM child_chunks WHERE tree_node_id = :node_id LIMIT 1'),
            {'node_id': str(node_id)}
        )
        kb_row = kb_result.first()
        kb_id = str(kb_row[0])

    # 召回测试
    print(f"\n=== 召回测试 ===")
    results = await parent_child_search(
        q_emb=q_emb,
        kb_ids=[kb_id],
        top_k=5
    )

    if results:
        first = results[0]
        print(f"\n召回结果:")
        print(f"  ID: {first.get('id')}")
        print(f"  标题: {first.get('title')}")
        print(f"  内容长度: {len(first.get('content', ''))}")
        print(f"  内容: {first.get('content')}")

        if first.get('id') == str(node_id):
            print(f"\n[OK] ID 匹配父分段")
        else:
            print(f"\n[ERROR] ID 不匹配")

        if first.get('content') == node['parent_content']:
            print(f"[OK] 内容是父分段内容")
        elif first.get('content') == child['content']:
            print(f"[INFO] 内容是子分段内容（与父分段相同）")
        else:
            print(f"[ERROR] 内容不匹配")
    else:
        print("没有召回结果")


if __name__ == "__main__":
    asyncio.run(test_single_child_chunk_node())
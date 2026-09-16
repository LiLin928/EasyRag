"""端到端测试：父子分段召回验证"""
import asyncio
import uuid
from sqlalchemy import text
from app.db.session import async_session
from app.core.retrieval.parent_child_search import parent_child_search, search_child_chunks


async def test_retrieval_returns_parent_not_child():
    """验证召回的是父分段而不是子分段"""

    # 1. 找一个有多个子分段的节点
    async with async_session() as session:
        result = await session.execute(
            text('''
                SELECT id, title, parent_content, child_chunk_count
                FROM doc_tree_nodes
                WHERE child_chunk_count > 1
                LIMIT 1
            ''')
        )
        node = result.mappings().first()

        if not node:
            print("没有找到多子分段节点，跳过测试")
            return

        node_id = node['id']
        print(f"测试节点: {node['title']}")
        print(f"节点 ID: {node_id}")
        print(f"parent_content 长度: {len(node['parent_content'])}")
        print(f"child_chunk_count: {node['child_chunk_count']}")

        # 查询该节点的子分段
        child_result = await session.execute(
            text('''
                SELECT id, position, content
                FROM child_chunks
                WHERE tree_node_id = :node_id
                ORDER BY position
                LIMIT 1
            '''),
            {'node_id': str(node_id)}
        )
        child = child_result.mappings().first()

        if not child:
            print("没有找到子分段")
            return

        child_id = child['id']
        child_content = child['content']
        print(f"\n第一个子分段 ID: {child_id}")
        print(f"子分段内容长度: {len(child_content)}")
        print(f"子分段内容前 100 字符: {child_content[:100]}")

        # 查询该节点所属的知识库
        kb_result = await session.execute(
            text('''
                SELECT DISTINCT kb_id
                FROM child_chunks
                WHERE tree_node_id = :node_id
                LIMIT 1
            '''),
            {'node_id': str(node_id)}
        )
        kb_row = kb_result.first()
        if not kb_row:
            print("没有找到知识库")
            return
        kb_id = str(kb_row[0])

    # 2. 使用子分段的内容作为查询（模拟向量相似检索）
    print(f"\n=== 开始测试召回 ===")
    print(f"使用子分段的前 200 字符作为查询文本")
    query_text = child_content[:200]

    # 3. 调用 search_child_chunks（模拟第一步：向量检索子分段）
    # 这里我们直接查询数据库，不使用向量
    async with async_session() as session:
        # 查询该子分段是否有 embedding
        emb_result = await session.execute(
            text('''
                SELECT embedding
                FROM child_chunks
                WHERE id = :child_id
            '''),
            {'child_id': str(child_id)}
        )
        emb_row = emb_result.first()

        if not emb_row or not emb_row[0]:
            print("子分段没有 embedding，跳过向量检索测试")
            return

        # 使用该子分段的 embedding 作为查询向量
        # 这样应该能召回这个子分段（或相似的子分段）
        q_emb_str = emb_row[0]
        print(f"使用子分段自身的 embedding 作为查询向量")

        # 解析 embedding
        import json
        # embedding 存储格式可能是字符串或数组
        if isinstance(q_emb_str, str):
            # 去除方括号，按逗号分割
            q_emb_str = q_emb_str.strip('[]')
            q_emb = [float(x) for x in q_emb_str.split(',')]
        else:
            q_emb = list(q_emb_str)

    # 4. 调用 parent_child_search
    print(f"\n调用 parent_child_search...")
    results = await parent_child_search(
        q_emb=q_emb,
        kb_ids=[kb_id],
        top_k=5
    )

    if not results:
        print("没有召回结果")
        return

    print(f"\n召回结果数量: {len(results)}")

    # 5. 检查第一个召回结果
    first_result = results[0]
    print(f"\n第一个召回结果:")
    print(f"  ID: {first_result.get('id')}")
    print(f"  document_id: {first_result.get('document_id')}")
    print(f"  标题: {first_result.get('title')}")
    print(f"  score: {first_result.get('score')}")
    print(f"  children 数量: {len(first_result.get('children', []))}")

    # 检查 ID 是否匹配
    result_id = first_result.get('id')
    if result_id == str(node_id):
        print(f"\n[SUCCESS] 召回的 ID 是父分段 ID（节点 ID）")
        print(f"   期望: {node_id}")
        print(f"   实际: {result_id}")
    else:
        print(f"\n[FAILED] 召回的 ID 不是父分段 ID")
        print(f"   期望父分段 ID: {node_id}")
        print(f"   实际 ID: {result_id}")
        print(f"   子分段 ID: {child_id}")
        if result_id == str(child_id):
            print(f"   [WARNING] 召回的是子分段 ID！")

    # 检查内容
    result_content = first_result.get('content', '')
    parent_content = node['parent_content']

    print(f"\n内容对比:")
    print(f"  召回内容长度: {len(result_content)}")
    print(f"  父分段内容长度: {len(parent_content)}")
    print(f"  召回内容前 100 字符: {result_content[:100]}")
    print(f"  父分段内容前 100 字符: {parent_content[:100]}")

    if result_content == parent_content:
        print(f"\n[SUCCESS] 召回的内容是完整的父分段内容")
    elif result_content == child_content:
        print(f"\n[FAILED] 召回的内容是子分段内容，不是父分段内容")
    else:
        print(f"\n[WARNING] 召回的内容既不是完整父分段也不是子分段")


if __name__ == "__main__":
    asyncio.run(test_retrieval_returns_parent_not_child())
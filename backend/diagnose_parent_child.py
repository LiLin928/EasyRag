"""诊断脚本：检查父子分段召回问题"""
import asyncio
import uuid
from sqlalchemy import text
from app.db.session import async_session
from app.core.retrieval.parent_child_search import parent_child_search
from app.providers.langchain_factory import build_embeddings


async def check_parent_content():
    """检查 doc_tree_nodes 表中的 parent_content 字段"""
    async with async_session() as session:
        # 查询所有树节点
        result = await session.execute(
            text("""
                SELECT id, title, parent_content, child_chunk_count
                FROM doc_tree_nodes
                LIMIT 10
            """)
        )
        rows = result.mappings().all()

        print("=== doc_tree_nodes 表数据 ===")
        for row in rows:
            print(f"ID: {row['id']}")
            print(f"标题: {row['title']}")
            print(f"parent_content 是否为 NULL: {row['parent_content'] is None}")
            print(f"parent_content 长度: {len(row['parent_content']) if row['parent_content'] else 0}")
            print(f"child_chunk_count: {row['child_chunk_count']}")
            print("-" * 80)


async def check_child_chunks():
    """检查 child_chunks 表数据"""
    async with async_session() as session:
        # 查询子分段
        result = await session.execute(
            text("""
                SELECT id, tree_node_id, content, position
                FROM child_chunks
                LIMIT 10
            """)
        )
        rows = result.mappings().all()

        print("\n=== child_chunks 表数据 ===")
        for row in rows:
            print(f"子分段 ID: {row['id']}")
            print(f"tree_node_id: {row['tree_node_id']}")
            print(f"position: {row['position']}")
            print(f"content 长度: {len(row['content']) if row['content'] else 0}")
            print(f"content 前 50 字符: {row['content'][:50] if row['content'] else 'NULL'}")
            print("-" * 80)


async def test_parent_child_search():
    """测试父子分段检索"""
    # 生成一个测试查询向量
    embeddings = await build_embeddings()
    test_query = "测试查询"
    q_emb = await embeddings.aembed_query(test_query)

    # 查询一个知识库 ID
    async with async_session() as session:
        kb_result = await session.execute(
            text("SELECT id FROM knowledge_bases LIMIT 1")
        )
        kb_row = kb_result.first()
        if not kb_row:
            print("没有找到知识库，跳过检索测试")
            return
        kb_id = str(kb_row[0])

    print(f"\n=== 测试父子分段检索 (kb_id={kb_id}) ===")
    results = await parent_child_search(
        q_emb=q_emb,
        kb_ids=[kb_id],
        top_k=3
    )

    print(f"返回结果数量: {len(results)}")
    for i, result in enumerate(results, 1):
        print(f"\n结果 {i}:")
        print(f"  ID: {result.get('id')}")
        print(f"  document_id: {result.get('document_id')}")
        print(f"  标题: {result.get('title')}")
        print(f"  内容来源: {result.get('content')[:100] if result.get('content') else 'NULL'}...")
        print(f"  score: {result.get('score')}")
        print(f"  children 数量: {len(result.get('children', []))}")
        if result.get('children'):
            print(f"  第一个 child ID: {result['children'][0].get('id')}")
            print(f"  第一个 child 内容: {result['children'][0].get('content')[:50] if result['children'][0].get('content') else 'NULL'}...")


async def main():
    """主函数"""
    print("开始诊断...")
    try:
        await check_parent_content()
        await check_child_chunks()
        await test_parent_child_search()
    except Exception as e:
        print(f"诊断出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
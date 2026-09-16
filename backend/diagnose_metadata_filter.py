"""诊断：元数据过滤对父子分段召回的影响"""
import asyncio
import json
from sqlalchemy import text
from app.db.session import async_session
from app.core.retrieval.parent_child_search import parent_child_search, search_child_chunks
from app.core.retrieval.metadata_filter import MetadataFilter


async def diagnose():
    run_id = 'b91eb855-3d9e-43cd-a4f8-6990654263c3'

    async with async_session() as session:
        # 1. 查询测试运行配置
        result = await session.execute(
            text('SELECT kb_id, config_snapshot FROM retrieval_test_runs WHERE id = :id'),
            {'id': run_id}
        )
        row = result.first()
        if not row:
            print(f'未找到测试运行: {run_id}')
            return

        kb_id = str(row[0])
        config = row[1]

        print('=== 测试配置 ===')
        print(f'知识库 ID: {kb_id}')
        print(f'检索模式: {config.get("retrieval_mode")}')
        print(f'document_metadata: {json.dumps(config.get("document_metadata"), ensure_ascii=False, indent=2)}')
        print(f'chunk_metadata: {json.dumps(config.get("chunk_metadata"), ensure_ascii=False, indent=2)}')

        # 2. 查询测试用例
        result = await session.execute(
            text('''
                SELECT query, results
                FROM retrieval_test_case_results
                WHERE run_id = :id
            '''),
            {'id': run_id}
        )
        case = result.first()
        if not case:
            print('未找到测试用例')
            return

        query = case[0]
        results = case[1]

        print(f'\n=== 测试用例 ===')
        print(f'查询: {query}')
        print(f'召回结果数量: {len(results)}')

        # 3. 分析召回结果
        for i, r in enumerate(results, 1):
            print(f'\n召回结果 {i}:')
            print(f'  父分段 ID (chunk_id): {r.get("chunk_id")}')
            print(f'  文档 ID: {r.get("document_id")}')
            print(f'  标题: {r.get("title")}')
            print(f'  score: {r.get("score")}')
            print(f'  children 数量: {len(r.get("children", []))}')

            if r.get('children'):
                print(f'  命中的子分段:')
                for j, child in enumerate(r['children'], 1):
                    print(f'    子分段 {j}:')
                    print(f'      ID: {child.get("id")}')
                    print(f'      position: {child.get("position")}')
                    print(f'      score: {child.get("score")}')
                    print(f'      内容长度: {len(child.get("content", ""))}')

        # 4. 检查"投标人须知"父分段的子分段数量
        print(f'\n=== "投标人须知"父分段分析 ===')
        result = await session.execute(
            text('''
                SELECT tn.id, tn.title, tn.child_chunk_count,
                       COUNT(c.id) as actual_child_count
                FROM doc_tree_nodes tn
                LEFT JOIN child_chunks c ON c.tree_node_id = tn.id AND c.enabled
                WHERE tn.title ILIKE '%投标人须知%'
                AND tn.document_id IN (
                    SELECT id FROM documents WHERE kb_id = :kb_id
                )
                GROUP BY tn.id, tn.title, tn.child_chunk_count
            '''),
            {'kb_id': kb_id}
        )
        nodes = result.mappings().all()

        for node in nodes:
            print(f'\n父分段: {node["title"]}')
            print(f'  ID: {node["id"]}')
            print(f'  记录的子分段数量: {node["child_chunk_count"]}')
            print(f'  实际的子分段数量: {node["actual_child_count"]}')

            # 查询子分段详情
            result2 = await session.execute(
                text('''
                    SELECT id, position, metadata
                    FROM child_chunks
                    WHERE tree_node_id = :node_id
                    AND enabled
                    ORDER BY position
                '''),
                {'node_id': str(node['id'])}
            )
            children = result2.mappings().all()

            print(f'  子分段列表:')
            for child in children:
                print(f'    position {child["position"]}: ID={child["id"]}, metadata={json.dumps(child["metadata"], ensure_ascii=False)}')


if __name__ == "__main__":
    asyncio.run(diagnose())
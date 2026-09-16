"""详细调试父子分段检索"""
import asyncio
from sqlalchemy import text
from app.db.session import async_session
from app.core.retrieval.parent_child_search import parent_child_search, search_child_chunks
from app.providers.langchain_factory import build_embeddings_from_config
from app.models.model_config import ModelConfig


async def debug_retrieval():
    async with async_session() as session:
        # 查询知识库
        result = await session.execute(
            text('SELECT id FROM knowledge_bases WHERE id = :id'),
            {'id': '938f4d6f-38ea-431b-a272-4dee8b0205ba'}
        )
        kb = result.first()
        if not kb:
            print('知识库不存在')
            return
        kb_id = str(kb[0])

        # 查询 embedding 模型
        result = await session.execute(
            text('''
                SELECT id, name, prov, params
                FROM model_configs
                WHERE id = '957cb987-7bd1-4087-8053-6fe70a24ee38'
            ''')
        )
        model_row = result.mappings().first()
        if not model_row:
            print('模型不存在')
            return

        # 构建 embedding 模型
        model_config = ModelConfig(
            id=model_row['id'],
            name=model_row['name'],
            prov=model_row['prov'],
            params=model_row['params'],
            enabled=True,
            grp='embed',
        )

        print('=== 模型配置 ===')
        print(f'name: {model_config.name}')
        print(f'prov: {model_config.prov}')

        embeddings = await build_embeddings_from_config(model_config)

        # 生成查询向量
        query_text = '投标人须知'
        print(f'\n=== 生成查询向量 ===')
        print(f'查询文本: {query_text}')

        q_emb = await embeddings.aembed_query(query_text)
        print(f'向量维度: {len(q_emb)}')
        print(f'向量前 10 个值: {q_emb[:10]}')

        # 第一步：检索子分段
        print(f'\n=== 步骤 1: 检索子分段 ===')
        children = await search_child_chunks(
            q_emb=q_emb,
            kb_ids=[kb_id],
            doc_ids=None,
            scope=None,
            top_k=15  # top_k * 3
        )

        print(f'召回子分段数量: {len(children)}')

        for i, child in enumerate(children[:5], 1):
            # 查询父分段标题
            result = await session.execute(
                text('SELECT title FROM doc_tree_nodes WHERE id = :id'),
                {'id': child['tree_node_id']}
            )
            node = result.first()

            print(f'\n子分段 {i}:')
            print(f'  ID: {child["id"]}')
            print(f'  tree_node_id: {child["tree_node_id"]}')
            print(f'  父分段标题: {node[0] if node else "未知"}')
            print(f'  vector_score: {child["vector_score"]}')

            if '投标人须知' in (node[0] if node else ''):
                print(f'  >>> 找到投标人须知！')

        # 第二步：映射回父分段
        print(f'\n=== 步骤 2: 映射回父分段 ===')
        results = await parent_child_search(
            q_emb=q_emb,
            kb_ids=[kb_id],
            top_k=5
        )

        print(f'召回父分段数量: {len(results)}')

        for i, parent in enumerate(results, 1):
            print(f'\n父分段 {i}:')
            print(f'  ID: {parent["id"]}')
            print(f'  标题: {parent["title"]}')
            print(f'  score: {parent["score"]}')
            print(f'  内容长度: {len(parent["content"])}')
            print(f'  children 数量: {len(parent["children"])}')

            if '投标人须知' in parent['title']:
                print(f'  >>> 找到投标人须知！')


if __name__ == "__main__":
    asyncio.run(debug_retrieval())
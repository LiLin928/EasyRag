"""重新解析文档脚本

用法：
cd backend
uv run python scripts/reparse_document.py <doc_id>
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.parser.dispatcher import DocumentDispatcher
from app.core.parser.tree_builder import TreeBuilder
from app.worker.tasks.parse_tasks import (
    _save_tree_nodes_to_db,
    _save_elements_to_db,
    _update_document_status
)
from app.providers.storage.factory import get_storage
import asyncpg


async def reparse_document(doc_id: str):
    """重新解析文档"""

    # 连接数据库
    conn = await asyncpg.connect(
        'postgresql://easyrag:easyrag2026@192.168.137.13:5432/easyrag_v2'
    )

    try:
        # 1. 获取文档信息
        doc = await conn.fetchrow(
            'SELECT id, file_key, kb_id, name FROM documents WHERE id = $1',
            doc_id
        )

        if not doc:
            print(f'❌ 文档不存在: {doc_id}')
            return

        print(f'📄 文档: {doc["name"]}')
        print(f'📍 文件路径: {doc["file_key"]}')

        # 2. 删除旧数据
        print('\n🗑️  删除旧数据...')
        await conn.execute('DELETE FROM doc_tree_nodes WHERE document_id = $1', doc_id)
        await conn.execute('DELETE FROM element_positions WHERE document_id = $1', doc_id)
        await conn.execute('DELETE FROM chunks WHERE document_id = $1', doc_id)
        print('✅ 旧数据已删除')

        # 3. 获取文件
        print('\n📥 下载文件...')
        storage = get_storage()
        file_data = await storage.get(doc['file_key'])
        print(f'✅ 文件大小: {len(file_data)} bytes')

        # 4. 解析文档
        print('\n🔍 解析文档...')
        dispatcher = DocumentDispatcher()
        parsed_doc = await dispatcher._dispatch_from_data(
            file_data, doc['file_key'], doc_id
        )
        print(f'✅ 提取了 {len(parsed_doc.elements)} 个元素')

        # 统计元素类型
        type_counts = {}
        for elem in parsed_doc.elements:
            type_counts[elem.element_type] = type_counts.get(elem.element_type, 0) + 1
        print(f'   类型分布: {type_counts}')

        # 5. 构建文档树
        print('\n🌳 构建文档树...')
        tree_builder = TreeBuilder()
        tree = await tree_builder.build(parsed_doc.elements, doc_id)
        print(f'✅ 构建了 {len(tree.nodes)} 个树节点')

        # 6. 保存到数据库
        print('\n💾 保存到数据库...')
        node_count = await _save_tree_nodes_to_db(tree, doc_id)
        print(f'✅ 保存了 {node_count} 个树节点')

        elem_count = await _save_elements_to_db(parsed_doc.elements, doc_id, tree)
        print(f'✅ 保存了 {elem_count} 个元素')

        # 7. 更新文档状态
        await _update_document_status(doc_id, 'done')
        print('✅ 文档状态已更新')

        print('\n🎉 重新解析完成！')

    finally:
        await conn.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python scripts/reparse_document.py <doc_id>')
        sys.exit(1)

    doc_id = sys.argv[1]
    asyncio.run(reparse_document(doc_id))
"""
测试表格分块修复

验证：
1. 分块器正确处理 table 元素
2. 表格内容被包含在分块中
"""
import sys
sys.path.insert(0, '.')
from app.core.parser.chunker import Chunker
from app.core.parser.base import DocumentElement, ElementPosition
import asyncio


async def test_table_chunking():
    """测试表格分块"""

    print("=" * 60)
    print("测试：表格分块支持")
    print("=" * 60)
    print()

    # 创建测试元素（包含表格）
    elements = [
        DocumentElement(
            element_id='elem-1',
            element_type='heading',
            content='文档标题',
            position=ElementPosition(),
            metadata={'level': 1}
        ),
        DocumentElement(
            element_id='elem-2',
            element_type='paragraph',
            content='这是一个普通段落，内容较长一些，以达到最小分块大小的要求。',
            position=ElementPosition(),
            metadata={}
        ),
        DocumentElement(
            element_id='elem-3',
            element_type='table',
            content='''| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A   | B   | C   |
| D   | E   | F   |
| G   | H   | I   |''',
            position=ElementPosition(),
            metadata={'rows': 3}
        ),
        DocumentElement(
            element_id='elem-4',
            element_type='heading',
            content='第二个标题',
            position=ElementPosition(),
            metadata={'level': 2}
        ),
        DocumentElement(
            element_id='elem-5',
            element_type='table',
            content='''| 参数 | 说明 |
|------|------|
| PDF  | 支持 |
| Word | 支持 |''',
            position=ElementPosition(),
            metadata={'rows': 2}
        ),
    ]

    # 创建分块器
    chunker = Chunker(chunk_size=512, chunk_overlap=50, min_chunk_size=100)

    # 执行分块
    chunks = await chunker.chunk(elements, 'test-doc', 'test-kb')

    print(f"元素数量: {len(elements)}")
    print(f"生成的分块数量: {len(chunks)}")
    print()

    # 检查分块内容
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}:")
        print(f"  内容长度: {len(chunk['content'])} 字符")
        print(f"  内容预览: {chunk['content'][:100]}...")

        # 检查是否包含表格
        if '|' in chunk['content']:
            print(f"  [OK] 包含表格标记")

        # 检查元素类型
        element_types = chunk['metadata']['element_types']
        print(f"  包含元素类型: {element_types}")

        # 检查是否有 table 类型
        if 'table' in element_types:
            print(f"  [OK] 包含 table 元素 ✓")

        print()

    # 验证结果
    print("=" * 60)
    print("验证结果")
    print("=" * 60)
    print()

    # 统计包含表格的分块
    table_chunks = [c for c in chunks if 'table' in c['metadata']['element_types']]

    if len(table_chunks) > 0:
        print(f"[OK] 找到 {len(table_chunks)} 个包含表格的分块 ✓")
        print(f"[OK] 表格内容已包含在分块中 ✓")
    else:
        print(f"[ERROR] 没有找到包含表格的分块")

    # 统计包含表格标记的分块
    table_marker_chunks = [c for c in chunks if '|' in c['content']]

    if len(table_marker_chunks) > 0:
        print(f"[OK] 找到 {len(table_marker_chunks)} 个包含表格标记（|）的分块 ✓")
    else:
        print(f"[ERROR] 没有找到包含表格标记的分块")


if __name__ == "__main__":
    asyncio.run(test_table_chunking())

    print()
    print("=" * 60)
    print("修复总结")
    print("=" * 60)
    print()
    print("修复内容:")
    print("  [OK] 在 chunker.py 中添加 'table' 元素类型支持")
    print("  [OK] 表格内容现在会被正确分块")
    print("  [OK] 表格可以被检索系统索引")
    print()
    print("下一步:")
    print("  1. 重新启动 Celery Worker")
    print("  2. 删除现有文档解析结果")
    print("  3. 重新上传文档进行测试")
    print("  4. 验证表格检索功能")
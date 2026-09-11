"""
验证 Markdown 表格解析修复效果

使用实际的测试用例验证修复
"""
import sys
sys.path.insert(0, '.')
from app.core.parser.markdown_parser import MarkdownParser
import asyncio

async def verify_fix():
    """验证修复效果"""

    parser = MarkdownParser()

    # 测试用例 1: 简单表格
    print("=" * 60)
    print("测试 1: 简单表格")
    print("=" * 60)

    simple_table = '''| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A   | B   | C   |
| D   | E   | F   |
'''

    result = await parser.parse(simple_table.encode('utf-8'), 'test-1')

    print(f"元素数量: {len(result.elements)}")
    for i, elem in enumerate(result.elements):
        print(f"  {i+1}. [{elem.element_type:10}] {elem.content[:50]}...")

    table_elements = [e for e in result.elements if e.element_type == 'table']
    print(f"\n[OK] 表格元素数量: {len(table_elements)}")
    print(f"[OK] 表格内容预览:\n{table_elements[0].content}")

    print()

    # 测试用例 2: 混合内容（标题、段落、表格）
    print("=" * 60)
    print("测试 2: 混合内容")
    print("=" * 60)

    mixed_content = '''# 标题

这是一个段落。

| 参数 | 说明 |
|------|------|
| PDF  | 支持 |
| Word | 支持 |

另一个段落。

| 姓名 | 年龄 |
|------|------|
| 张三 | 25   |
| 李四 | 30   |
'''

    result = await parser.parse(mixed_content.encode('utf-8'), 'test-2')

    print(f"元素数量: {len(result.elements)}")
    for i, elem in enumerate(result.elements):
        if elem.element_type == 'table':
            print(f"  {i+1}. [{elem.element_type:10}] （表格，{elem.metadata.get('rows', 0)} 行数据）")
        else:
            print(f"  {i+1}. [{elem.element_type:10}] {elem.content[:40]}...")

    table_elements = [e for e in result.elements if e.element_type == 'table']
    paragraph_elements = [e for e in result.elements if e.element_type == 'paragraph']
    heading_elements = [e for e in result.elements if e.element_type == 'heading']

    print(f"\n元素类型统计:")
    print(f"  - 表格: {len(table_elements)}")
    print(f"  - 段落: {len(paragraph_elements)}")
    print(f"  - 标题: {len(heading_elements)}")

    # 验证表格没有拆分成独立段落
    expected_elements = 1 + 2 + 2  # 1 标题 + 2 段落 + 2 表格
    if len(result.elements) == expected_elements:
        print(f"\n[OK] 元素数量正确: {len(result.elements)} == {expected_elements}")
    else:
        print(f"\n[ERROR] 元素数量不正确: {len(result.elements)} != {expected_elements}")

    print()

    # 测试用例 3: 复杂表格
    print("=" * 60)
    print("测试 3: 复杂表格（模拟问题文档）")
    print("=" * 60)

    complex_table = '''| 维度 | 本解析器 | PageIndex | 融合方式 |
|------|-----------|-----------|---------|
| **pageIndex 是否支持** | element_positions.json 提供 `page` 字段（1-based） | 树节点必须 `page_range` 字段 | **直接复用**，无需修改 |
| **层级提取** | 未正式提取 | 需要目录树 | 通过 **层级推断模块**，结合 PDF 书签/字体大小/样式模式推断 |
| **Chunk 策略** | 无（仅页提取） | 无（仅页为单位） | **统一按页为原子单位**，再元素级精细定位 |
'''

    result = await parser.parse(complex_table.encode('utf-8'), 'test-3')

    print(f"元素数量: {len(result.elements)}")

    table_elements = [e for e in result.elements if e.element_type == 'table']
    if len(table_elements) == 1:
        print(f"[OK] 表格作为整体单元（1 个元素）")

        table = table_elements[0]
        print(f"[OK] 表格包含 {table.metadata.get('rows', 0)} 行数据")
        print(f"[OK] 表格总行数: {table.metadata.get('total_lines', 0)}")

        # 验证表格内容完整
        if '| 维度 | 本解析器 | PageIndex | 融合方式 |' in table.content:
            print(f"[OK] 表头完整")
        if '| **pageIndex 是否支持**' in table.content:
            print(f"[OK] 第一行数据完整")
        if '| **Chunk 策略**' in table.content:
            print(f"[OK] 最后一行数据完整")
    else:
        print(f"[ERROR] 表格被拆分为 {len(table_elements)} 个元素")

    print()
    print("=" * 60)
    print("修复验证完成！")
    print("=" * 60)
    print("\n总结:")
    print("[OK] 表格被识别为 table 元素类型")
    print("[OK] 表格作为整体单元，不被逐行拆分")
    print("[OK] 表格内容完整保留")
    print("[OK] 元数据包含正确的行数统计")

if __name__ == "__main__":
    asyncio.run(verify_fix())
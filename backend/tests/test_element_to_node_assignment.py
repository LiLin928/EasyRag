"""测试元素到树节点的分配逻辑"""
import pytest
from app.core.parser.tree_builder import TreeBuilder
from app.core.parser.base import DocumentElement, ElementPosition


@pytest.mark.asyncio
async def test_assign_elements_to_nodes():
    """测试元素正确分配到树节点"""
    # 创建测试元素
    elements = [
        DocumentElement(
            element_id='elem-1',
            element_type='heading',
            content='1. 概述',
            position=ElementPosition(page=1),
            metadata={'level': 1}
        ),
        DocumentElement(
            element_id='elem-2',
            element_type='paragraph',
            content='这是第一段内容',
            position=ElementPosition(page=1),
            metadata={}
        ),
        DocumentElement(
            element_id='elem-3',
            element_type='list',
            content='- 列表项1',
            position=ElementPosition(page=1),
            metadata={}
        ),
        DocumentElement(
            element_id='elem-4',
            element_type='heading',
            content='1.1 目标',
            position=ElementPosition(page=1),
            metadata={'level': 2}
        ),
        DocumentElement(
            element_id='elem-5',
            element_type='paragraph',
            content='这是第二段内容',
            position=ElementPosition(page=1),
            metadata={}
        ),
    ]

    # 构建树
    builder = TreeBuilder()
    tree = await builder.build(elements, 'test-doc-id')

    # 验证树节点数量
    assert len(tree.nodes) == 2  # 两个标题节点

    # 验证第一个节点包含的元素
    first_node = tree.nodes[0]
    assert first_node.title == '1. 概述'
    assert 'elem-1' in first_node.element_ids  # 标题自己
    assert 'elem-2' in first_node.element_ids  # 段落
    assert 'elem-3' in first_node.element_ids  # 列表

    # 验证第二个节点包含的元素
    second_node = tree.nodes[1]
    assert second_node.title == '1.1 目标'
    assert 'elem-4' in second_node.element_ids  # 标题自己
    assert 'elem-5' in second_node.element_ids  # 段落


@pytest.mark.asyncio
async def test_assign_elements_with_no_headings():
    """测试没有标题时的元素分配"""
    elements = [
        DocumentElement(
            element_id='elem-1',
            element_type='paragraph',
            content='纯文本内容',
            position=ElementPosition(page=1),
            metadata={}
        ),
    ]

    builder = TreeBuilder()
    tree = await builder.build(elements, 'test-doc-id')

    # 应该创建根节点
    assert len(tree.nodes) == 1
    root_node = tree.nodes[0]
    assert root_node.title == 'Root'
    # 根节点应该包含所有元素
    assert 'elem-1' in root_node.element_ids


@pytest.mark.asyncio
async def test_assign_elements_to_last_heading():
    """测试最后一个标题下的元素分配"""
    elements = [
        DocumentElement(
            element_id='elem-1',
            element_type='heading',
            content='最终章节',
            position=ElementPosition(page=1),
            metadata={'level': 1}
        ),
        DocumentElement(
            element_id='elem-2',
            element_type='paragraph',
            content='最后一段',
            position=ElementPosition(page=1),
            metadata={}
        ),
        DocumentElement(
            element_id='elem-3',
            element_type='code',
            content='print("hello")',
            position=ElementPosition(page=1),
            metadata={}
        ),
    ]

    builder = TreeBuilder()
    tree = await builder.build(elements, 'test-doc-id')

    # 验证最后一个标题节点包含所有后续元素
    assert len(tree.nodes) == 1
    node = tree.nodes[0]
    assert 'elem-1' in node.element_ids
    assert 'elem-2' in node.element_ids
    assert 'elem-3' in node.element_ids
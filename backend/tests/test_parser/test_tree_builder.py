# backend/tests/test_parser/test_tree_builder.py
"""TreeBuilder 测试"""

import pytest
from app.core.parser.tree_builder import TreeBuilder
from app.core.parser.base import DocumentElement, ElementPosition


@pytest.fixture
def builder():
    return TreeBuilder()


def create_heading_element(level: int, title: str) -> DocumentElement:
    """创建标题元素"""
    return DocumentElement(
        element_id=f'elem-{level}-{title}',
        element_type='heading',
        content=title,
        position=ElementPosition(),
        metadata={'level': level}
    )


def create_paragraph_element(text: str) -> DocumentElement:
    """创建段落元素"""
    return DocumentElement(
        element_id=f'elem-{text}',
        element_type='paragraph',
        content=text,
        position=ElementPosition(),
        metadata={}
    )


@pytest.mark.asyncio
async def test_build_simple_tree(builder):
    """测试构建简单树"""
    elements = [
        create_heading_element(1, 'Chapter 1'),
        create_paragraph_element('Content 1'),
        create_heading_element(2, 'Section 1.1'),
        create_paragraph_element('Content 2'),
    ]

    tree = await builder.build(elements, 'test-doc')

    assert tree is not None
    assert len(tree.nodes) >= 2  # 至少有 2 个标题节点


@pytest.mark.asyncio
async def test_heading_level_detection(builder):
    """测试标题层级检测"""
    elements = [
        create_heading_element(1, 'Level 1'),
        create_heading_element(2, 'Level 2'),
        create_heading_element(3, 'Level 3'),
    ]

    tree = await builder.build(elements, 'test-doc')

    # 验证层级关系
    level_nodes = {node.level for node in tree.nodes}
    assert 1 in level_nodes
    assert 2 in level_nodes
    assert 3 in level_nodes


@pytest.mark.asyncio
async def test_tree_parent_child_relationship(builder):
    """测试父子关系构建"""
    elements = [
        create_heading_element(1, 'Parent'),
        create_heading_element(2, 'Child 1'),
        create_heading_element(2, 'Child 2'),
    ]

    tree = await builder.build(elements, 'test-doc')

    # 找到父节点
    parent = next((n for n in tree.nodes if n.title == 'Parent'), None)
    assert parent is not None
    assert len(parent.children) == 2
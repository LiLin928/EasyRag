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
async def test_heading_node_ids_are_valid_uuids(builder):
    """标题节点的 node_id 必须是合法 UUID 字符串。

    下游 _save_child_chunks_to_db 用 uuid.UUID(tree_node_id) 解析，
    且 ChildChunk.tree_node_id 是指向 doc_tree_nodes.id 的 UUID 外键，
    因此 TreeBuilder 产出的 node_id 必须可直接被 uuid.UUID 解析。
    回归：曾用 f'{doc_id}-node-{elem_id}' 复合字符串导致解析任务抛
    ValueError('badly formed hexadecimal UUID string')。
    """
    import uuid
    elements = [
        create_heading_element(1, 'Chapter 1'),
        create_paragraph_element('Content 1'),
        create_heading_element(2, 'Section 1.1'),
        create_paragraph_element('Content 2'),
    ]
    tree = await builder.build(elements, str(uuid.uuid4()))
    assert tree.nodes
    for node in tree.nodes:
        # 不应抛 ValueError；且与 DB 主键一致由 _save_tree_nodes_to_db 保证
        uuid.UUID(node.node_id)


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
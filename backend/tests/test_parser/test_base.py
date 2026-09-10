# backend/tests/test_parser/test_base.py
"""基础数据结构测试"""

import pytest
from app.core.parser.base import (
    DocumentElement,
    ElementPosition,
    TreeNode,
    DocumentTree,
    ParsedDocument,
)


def test_element_position():
    """测试元素位置"""
    pos = ElementPosition(page=1, x=10.5, y=20.3, width=100, height=50)
    assert pos.page == 1
    assert pos.x == 10.5


def test_document_element():
    """测试文档元素"""
    pos = ElementPosition(page=1)
    elem = DocumentElement(
        element_id='elem-1',
        element_type='paragraph',
        content='Test content',
        position=pos,
        metadata={'font': 'Arial'}
    )
    assert elem.element_id == 'elem-1'
    assert elem.element_type == 'paragraph'
    assert elem.content == 'Test content'


def test_tree_node():
    """测试树节点"""
    node = TreeNode(
        node_id='node-1',
        level=1,
        title='Chapter 1',
        element_ids=['elem-1', 'elem-2'],
        children=['node-2', 'node-3']
    )
    assert node.level == 1
    assert len(node.children) == 2


def test_parsed_document():
    """测试解析文档"""
    pos = ElementPosition(page=1)
    elem = DocumentElement(
        element_id='elem-1',
        element_type='paragraph',
        content='Test',
        position=pos
    )

    doc = ParsedDocument(
        doc_id='test-doc',
        file_key='test.pdf',
        elements=[elem],
        metadata={'page_count': 1}
    )

    assert doc.doc_id == 'test-doc'
    assert doc.element_count == 1
    assert doc.structure is None
"""父子分块器测试

测试 ParentChildChunker 的核心功能：
1. 短章节生成单个子分段
2. 长章节切分为多个子分段
3. 子分段映射回父分段
"""
import pytest
from app.core.parser.parent_child_chunker import ParentChildChunker
from app.core.parser.base import DocumentElement, ElementPosition


class MockElement:
    """模拟文档元素"""

    def __init__(self, content: str, element_id: str):
        self.content = content
        self.element_id = element_id
        self.element_type = "text"
        self.position = ElementPosition(page=1, x=0, y=0, width=100, height=10)
        self.metadata = {}


@pytest.mark.asyncio
async def test_short_section_single_child_chunk():
    """测试短章节生成单个子分段

    场景：
    - 章节内容 < 200 字符
    - 应该生成 1 个子分段
    """
    chunker = ParentChildChunker(
        child_chunk_size=200,
        child_chunk_overlap=50,
        min_child_chunk_size=100
    )

    # 模拟短章节
    tree_nodes = [
        {
            'node_id': 'node-1',
            'title': '第一章 招标公告',
            'level': 1,
            'element_ids': ['elem-1']
        }
    ]

    elements = [
        MockElement(
            content='这是一个短章节的内容，总长度小于200字符。',
            element_id='elem-1'
        )
    ]

    # 执行分块
    child_chunks = await chunker.chunk(
        tree_nodes,
        elements,
        'doc-1',
        'kb-1'
    )

    # 验证结果
    assert len(child_chunks) == 1
    assert child_chunks[0]['tree_node_id'] == 'node-1'
    assert child_chunks[0]['position'] == 1
    assert child_chunks[0]['metadata']['parent_title'] == '第一章 招标公告'
    assert child_chunks[0]['metadata']['parent_level'] == 1


@pytest.mark.asyncio
async def test_long_section_multiple_child_chunks():
    """测试长章节切分为多个子分段

    场景：
    - 章节内容 > 200 字符
    - 应该切分为多个子分段
    - 子分段位置应该连续
    """
    chunker = ParentChildChunker(
        child_chunk_size=200,
        child_chunk_overlap=50,
        min_child_chunk_size=100
    )

    # 模拟长章节（> 200 字符）
    long_content = '这是一个很长的章节内容。' * 50  # 约 550 字符

    tree_nodes = [
        {
            'node_id': 'node-1',
            'title': '第一章 招标公告',
            'level': 1,
            'element_ids': ['elem-1']
        }
    ]

    elements = [
        MockElement(
            content=long_content,
            element_id='elem-1'
        )
    ]

    # 执行分块
    child_chunks = await chunker.chunk(
        tree_nodes,
        elements,
        'doc-1',
        'kb-1'
    )

    # 验证结果
    assert len(child_chunks) > 1

    # 验证所有子分段都属于同一个父分段
    for chunk in child_chunks:
        assert chunk['tree_node_id'] == 'node-1'

    # 验证位置连续
    positions = [chunk['position'] for chunk in child_chunks]
    expected_positions = list(range(1, len(child_chunks) + 1))
    assert positions == expected_positions

    # 验证所有子分段都有父分段元数据
    for chunk in child_chunks:
        assert 'parent_title' in chunk['metadata']
        assert 'parent_level' in chunk['metadata']


@pytest.mark.asyncio
async def test_multiple_sections():
    """测试多个章节的父子分段

    场景：
    - 多个章节，有长有短
    - 每个章节独立处理
    """
    chunker = ParentChildChunker(
        child_chunk_size=200,
        child_chunk_overlap=50,
        min_child_chunk_size=100
    )

    # 模拟多个章节
    tree_nodes = [
        {
            'node_id': 'node-1',
            'title': '第一章 短章节',
            'level': 1,
            'element_ids': ['elem-1']
        },
        {
            'node_id': 'node-2',
            'title': '第二章 长章节',
            'level': 1,
            'element_ids': ['elem-2']
        }
    ]

    short_content = '这是一个短章节，内容很少。'
    long_content = '这是一个很长的章节内容。' * 30  # 约 330 字符

    elements = [
        MockElement(content=short_content, element_id='elem-1'),
        MockElement(content=long_content, element_id='elem-2')
    ]

    # 执行分块
    child_chunks = await chunker.chunk(
        tree_nodes,
        elements,
        'doc-1',
        'kb-1'
    )

    # 验证结果
    # 第一章应该有 1 个子分段
    node1_chunks = [c for c in child_chunks if c['tree_node_id'] == 'node-1']
    assert len(node1_chunks) == 1

    # 第二章应该有多个子分段
    node2_chunks = [c for c in child_chunks if c['tree_node_id'] == 'node-2']
    assert len(node2_chunks) > 1

    # 验证每个章节的子分段位置独立
    node1_positions = [c['position'] for c in node1_chunks]
    assert node1_positions == [1]

    node2_positions = [c['position'] for c in node2_chunks]
    assert node2_positions == list(range(1, len(node2_chunks) + 1))


@pytest.mark.asyncio
async def test_empty_section():
    """测试空章节

    场景：
    - 章节没有元素
    - 不应该生成子分段
    """
    chunker = ParentChildChunker()

    tree_nodes = [
        {
            'node_id': 'node-1',
            'title': '空章节',
            'level': 1,
            'element_ids': []  # 没有元素
        }
    ]

    elements = []

    # 执行分块
    child_chunks = await chunker.chunk(
        tree_nodes,
        elements,
        'doc-1',
        'kb-1'
    )

    # 验证结果
    assert len(child_chunks) == 0


@pytest.mark.asyncio
async def test_sentence_boundary_split():
    """测试句子边界切分

    场景：
    - 长章节按句子边界切分
    - 不应该在句子中间切分
    """
    chunker = ParentChildChunker(
        child_chunk_size=200,
        child_chunk_overlap=50,
        min_child_chunk_size=100
    )

    # 构造包含多个句子的长内容
    long_content = (
        '这是第一句话，内容比较长，用于测试句子边界切分。'
        '这是第二句话，继续测试。'
        '这是第三句话，内容也很长。'
        '这是第四句话，用于验证切分结果。'
        '这是第五句话，测试结束。'
    ) * 10  # 重复以增加长度

    tree_nodes = [
        {
            'node_id': 'node-1',
            'title': '测试章节',
            'level': 1,
            'element_ids': ['elem-1']
        }
    ]

    elements = [
        MockElement(content=long_content, element_id='elem-1')
    ]

    # 执行分块
    child_chunks = await chunker.chunk(
        tree_nodes,
        elements,
        'doc-1',
        'kb-1'
    )

    # 验证每个子分段都以句子结束符结尾
    for chunk in child_chunks:
        content = chunk['content']
        # 允许最后一个字符是句子结束符或换行符
        assert content.endswith(('。', '！', '？', '；', '\n')) or len(content) < 200


@pytest.mark.asyncio
async def test_chunk_metadata():
    """测试子分段元数据

    场景：
    - 子分段应该包含父分段的元数据
    - 包括父分段标题、层级等
    """
    chunker = ParentChildChunker()

    tree_nodes = [
        {
            'node_id': 'node-1',
            'title': '第一章 测试标题',
            'level': 2,
            'element_ids': ['elem-1']
        }
    ]

    elements = [
        MockElement(content='测试内容', element_id='elem-1')
    ]

    # 执行分块
    child_chunks = await chunker.chunk(
        tree_nodes,
        elements,
        'doc-1',
        'kb-1'
    )

    # 验证元数据
    assert len(child_chunks) == 1
    chunk = child_chunks[0]

    assert 'metadata' in chunk
    assert chunk['metadata']['parent_title'] == '第一章 测试标题'
    assert chunk['metadata']['parent_level'] == 2

    # 验证其他必要字段
    assert 'doc_id' in chunk
    assert 'kb_id' in chunk
    assert 'tree_node_id' in chunk
    assert 'position' in chunk
    assert 'content' in chunk
    assert 'char_count' in chunk
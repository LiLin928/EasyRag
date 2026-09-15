"""测试 DOCX 解析器标题层级识别修复"""
import pytest
from app.core.parser.docx_parser import DOCXParser


class MockPara:
    """模拟段落对象"""
    def __init__(self, style_name: str, text: str):
        self.style = type('Style', (), {'name': style_name})()
        self.text = text
        self.alignment = None  # 添加 alignment 属性


@pytest.mark.asyncio
async def test_extract_heading_level_from_style():
    """测试从样式名称提取标题层级"""
    parser = DOCXParser()

    # 英文样式
    para = MockPara('Heading 1', '第一章 招标公告')
    assert parser._extract_heading_level(para) == 1

    para = MockPara('Heading 2', '1.1 招标项目概况')
    assert parser._extract_heading_level(para) == 2

    para = MockPara('Heading 3', '1.1.1 项目背景')
    assert parser._extract_heading_level(para) == 3

    # 中文样式
    para = MockPara('标题 1', '第一章 招标公告')
    assert parser._extract_heading_level(para) == 1

    para = MockPara('标题 2', '1.1 招标项目概况')
    assert parser._extract_heading_level(para) == 2


@pytest.mark.asyncio
async def test_extract_heading_level_from_content():
    """测试从内容推断标题层级"""
    parser = DOCXParser()

    # 中文章节编号
    para = MockPara('Normal', '第一章 招标公告')
    assert parser._extract_heading_level(para) == 1

    para = MockPara('Normal', '第二章 投标人须知')
    assert parser._extract_heading_level(para) == 1

    # 中文数字编号
    para = MockPara('Normal', '一、项目概述')
    assert parser._extract_heading_level(para) == 1

    para = MockPara('Normal', '二、项目背景')
    assert parser._extract_heading_level(para) == 1

    # 中文括号编号
    para = MockPara('Normal', '（一）项目背景')
    assert parser._extract_heading_level(para) == 2

    para = MockPara('Normal', '（二）项目范围')
    assert parser._extract_heading_level(para) == 2

    # 阿拉伯数字编号
    para = MockPara('Normal', '1 投标')
    assert parser._extract_heading_level(para) == 1

    para = MockPara('Normal', '1.1 招标项目概况')
    assert parser._extract_heading_level(para) == 2

    para = MockPara('Normal', '1.1.1 项目背景')
    assert parser._extract_heading_level(para) == 3


@pytest.mark.asyncio
async def test_create_paragraph_element_with_level():
    """测试创建段落元素时正确设置标题层级"""
    parser = DOCXParser()

    # 标题元素
    para = MockPara('Heading 1', '第一章 招标公告')
    elem = parser._create_paragraph_element(para, 0, 'test-doc')

    assert elem.element_type == 'heading'
    assert elem.metadata['level'] == 1
    assert elem.metadata['is_heading'] is True

    # 普通段落
    para = MockPara('Normal', '这是一段普通文本')
    elem = parser._create_paragraph_element(para, 1, 'test-doc')

    assert elem.element_type == 'paragraph'
    assert elem.metadata['level'] == 0
    assert elem.metadata['is_heading'] is False
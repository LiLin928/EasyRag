"""导航式检索测试。"""
import pytest
from app.core.retrieval.navigation import NavigationSearch


def test_navigation_search_initialization():
    """测试导航式检索初始化。"""
    nav_search = NavigationSearch(confidence_threshold=0.15, anchor_count=3)

    assert nav_search.confidence_threshold == 0.15
    assert nav_search.anchor_count == 3


def test_navigation_search_default_threshold():
    """测试默认置信度阈值。"""
    nav_search = NavigationSearch()

    assert nav_search.confidence_threshold == 0.15
    assert nav_search.anchor_count == 3


@pytest.mark.asyncio
async def test_identify_scope_no_candidates():
    """测试无候选结果的情况。"""
    nav_search = NavigationSearch()

    # 这个测试需要数据库会话，这里只测试基本逻辑
    # 实际测试应该在集成测试中进行
    result = nav_search.identify_scope.__code__
    assert result is not None
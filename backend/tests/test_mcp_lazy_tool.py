"""测试 MCP 延迟加载工具。"""
import asyncio

import pytest

from app.core.agent.tool_registry_lazy import _mcp_lazy_tool
from app.models.mcp import Mcp


@pytest.fixture
def mock_mcp():
    """创建模拟的 MCP 配置。"""
    return Mcp(
        id="test-mcp-id",
        name="duckduckgo-search",
        status="on",
        tool_count=2,
    )


@pytest.mark.asyncio
async def test_mcp_lazy_tool_with_query(mock_mcp):
    """测试使用 query 参数调用工具。"""
    tool = _mcp_lazy_tool(mock_mcp)

    print(f"\n测试工具: {tool.name}")
    print(f"工具描述: {tool.description}")

    # 调用工具
    result = await tool.ainvoke({'query': '长电科技 股票'})

    print(f"\n工具返回结果（前500字符）:")
    print(result[:500])

    # 验证结果
    success = "Found" in result or "search results" in result

    if success:
        print(f"\n[SUCCESS] 测试通过: 返回了真实的搜索结果")
    else:
        print(f"\n[FAILED] 测试失败: 未返回搜索结果")

    assert success, "工具应该返回真实的搜索结果"


@pytest.mark.asyncio
async def test_mcp_lazy_tool_with_tool_name(mock_mcp):
    """测试明确指定工具名称。"""
    tool = _mcp_lazy_tool(mock_mcp)

    print(f"\n测试明确指定工具名称")

    # 调用工具
    result = await tool.ainvoke({
        'tool_name': 'search',
        'query': '长江电力'
    })

    print(f"\n工具返回结果（前300字符）:")
    print(result[:300])

    # 验证结果
    success = "Found" in result or "search results" in result

    if success:
        print(f"\n[SUCCESS] 测试通过: 成功指定工具名称")
    else:
        print(f"\n[FAILED] 测试失败")

    assert success, "应该返回搜索结果"


@pytest.mark.asyncio
async def test_mcp_lazy_tool_parameter_compatibility(mock_mcp):
    """测试参数兼容性。"""
    tool = _mcp_lazy_tool(mock_mcp)

    print(f"\n测试参数兼容性")

    # 测试不同的参数格式
    test_cases = [
        ({'query': 'test'}, "简单查询"),
        ({'tool_name': 'search', 'query': 'test'}, "指定工具名"),
    ]

    for params, desc in test_cases:
        print(f"\n测试参数格式: {desc}")
        print(f"参数: {params}")

        result = await tool.ainvoke(params)

        # 检查是否是真实结果
        if "Found" in result or "search results" in result:
            print(f"[PASS] {desc}: 返回真实结果")
        elif "已就绪" in result:
            print(f"[FAIL] {desc}: 仍返回占位符")
        else:
            print(f"[?] {desc}: 其他结果")


if __name__ == "__main__":
    # 直接运行测试
    mock = Mcp(
        id="test-mcp-id",
        name="duckduckgo-search",
        status="on",
        tool_count=2,
    )

    print("="*60)
    print("开始 MCP 延迟加载工具测试")
    print("="*60)

    asyncio.run(test_mcp_lazy_tool_with_query(mock))
    asyncio.run(test_mcp_lazy_tool_with_tool_name(mock))
    asyncio.run(test_mcp_lazy_tool_parameter_compatibility(mock))

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
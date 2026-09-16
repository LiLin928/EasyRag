"""使用延迟加载的示例"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.models.agent import Agent
from app.core.agent.tool_registry_lazy import build_tools

async def test_lazy_loading():
    """测试延迟加载效果"""

    # 创建一个模拟的智能体配置
    agent = Agent(
        id="test-agent",
        name="测试智能体",
        tools=["tool1"],  # 工具ID
        mcps=["mcp1", "mcp2", "mcp3"],  # 多个MCP服务
        skills=["skill1"],
        wfs=[],
        docs=[]
    )

    print("测试1：立即加载所有工具（传统方式）")
    print("=" * 60)
    import time
    start = time.time()
    tools_eager = await build_tools(agent, lazy_mcp=False)
    elapsed_eager = time.time() - start
    print(f"工具数量：{len(tools_eager)}")
    print(f"加载时间：{elapsed_eager:.2f}s")
    print(f"工具列表：{[t.name for t in tools_eager]}")

    print("\n测试2：延迟加载 MCP（优化方式）")
    print("=" * 60)
    start = time.time()
    tools_lazy = await build_tools(agent, lazy_mcp=True)
    elapsed_lazy = time.time() - start
    print(f"工具数量：{len(tools_lazy)}")
    print(f"加载时间：{elapsed_lazy:.2f}s")
    print(f"工具列表：{[t.name for t in tools_lazy]}")

    print("\n性能对比：")
    print(f"时间节省：{(elapsed_eager - elapsed_lazy) / elapsed_eager * 100:.1f}%")

if __name__ == "__main__":
    asyncio.run(test_lazy_loading())
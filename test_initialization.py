"""测试智能体初始化"""
import asyncio
import sys
import time
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from sqlalchemy import select
from app.db.session import async_session
from app.models.agent import Agent
from app.core.agent.tool_registry_lazy import build_tools

async def test_initialization():
    """测试智能体初始化是否成功"""

    print("测试智能体初始化")
    print("=" * 60)

    async with async_session() as s:
        agent = (await s.execute(
            select(Agent).where(Agent.id == "545d7c33-0a98-4af6-afc3-f73b0f282efb")
        )).scalar_one_or_none()

        if not agent:
            print("❌ 智能体不存在")
            return

        print(f"智能体名称: {agent.name}")
        print(f"工具数量: {len(agent.tools or [])}")
        print(f"MCP数量: {len(agent.mcps or [])}")
        print(f"技能数量: {len(agent.skills or [])}")

        # 测试延迟加载
        print("\n测试延迟加载...")
        start = time.time()

        try:
            tools = await build_tools(agent, lazy_mcp=True)
            elapsed = time.time() - start

            print(f"✅ 初始化成功")
            print(f"工具数量: {len(tools)}")
            print(f"加载时间: {elapsed:.2f}s")
            print(f"工具列表: {[t.name for t in tools]}")

        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_initialization())
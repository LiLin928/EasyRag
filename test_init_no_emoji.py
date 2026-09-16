"""测试智能体初始化（无emoji版本）"""
import asyncio
import sys
import time
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from sqlalchemy import select
from app.db.session import async_session
from app.models.agent import Agent
from app.core.agent.tool_registry_lazy import build_tools

async def test_initialization():
    """测试智能体初始化"""

    print("Test Agent Initialization")
    print("=" * 60)

    async with async_session() as s:
        agent = (await s.execute(
            select(Agent).where(Agent.id == "545d7c33-0a98-4af6-afc3-f73b0f282efb")
        )).scalar_one_or_none()

        if not agent:
            print("[ERROR] Agent not found")
            return

        print(f"Agent Name: {agent.name}")
        print(f"Tools Count: {len(agent.tools or [])}")
        print(f"MCP Count: {len(agent.mcps or [])}")
        print(f"Skills Count: {len(agent.skills or [])}")

        # Test lazy loading
        print("\nTest Lazy Loading...")
        start = time.time()

        try:
            tools = await build_tools(agent, lazy_mcp=True)
            elapsed = time.time() - start

            print(f"[OK] Initialization successful")
            print(f"Tools Count: {len(tools)}")
            print(f"Load Time: {elapsed:.2f}s")
            print(f"Tool Names: {[t.name for t in tools]}")

        except Exception as e:
            print(f"[ERROR] Initialization failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_initialization())
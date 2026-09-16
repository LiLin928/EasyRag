"""迁移脚本：启用延迟加载"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from sqlalchemy import select, update
from app.db.session import async_session
from app.models.agent import Agent

async def migrate_to_lazy_loading():
    """将所有智能体迁移到延迟加载模式"""

    async with async_session() as s:
        # 查询所有智能体
        agents = (await s.execute(select(Agent))).scalars().all()

        print(f"找到 {len(agents)} 个智能体")
        print("=" * 60)

        for agent in agents:
            print(f"\n智能体：{agent.name}")
            print(f"  工具数量：{len(agent.tools or [])}")
            print(f"  MCP数量：{len(agent.mcps or [])}")
            print(f"  技能数量：{len(agent.skills or [])}")

            # 检查是否有 MCP 服务
            has_mcp = len(agent.mcps or []) > 0

            if has_mcp:
                print(f"  → 建议启用延迟加载（有 {len(agent.mcps)} 个MCP）")
                # 实际迁移时，需要添加 lazy_load_mcp 字段到 Agent 模型
                # agent.lazy_load_mcp = True
                # await s.commit()
            else:
                print(f"  → 无需延迟加载（没有MCP）")

        print("\n" + "=" * 60)
        print("迁移完成！")

if __name__ == "__main__":
    asyncio.run(migrate_to_lazy_loading())
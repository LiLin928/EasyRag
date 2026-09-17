"""
检查 MCP 和工具状态
"""
import asyncio
import sys
import json

sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from sqlalchemy import select
from app.db.session import async_session
from app.models.agent import Agent
from app.models.mcp import Mcp
from app.models.tool import Tool
from app.core.agent.tool_adapters.mcp_tools import test_connection
from app.services.tool_service import execute_tool


async def check_mcp_status():
    """检查 MCP 状态"""

    print("=" * 80)
    print("1. MCP 状态检查")
    print("=" * 80)

    async with async_session() as s:
        mcps = (await s.execute(select(Mcp))).scalars().all()

        if not mcps:
            print("数据库中没有 MCP 配置")
            return []

        print(f"\n找到 {len(mcps)} 个 MCP 配置:\n")

        results = []
        for mcp in mcps:
            print(f"MCP: {mcp.name}")
            print(f"  类型: {mcp.tp}")
            print(f"  状态: {mcp.status}")
            print(f"  工具数量: {mcp.tool_count}")

            if mcp.status == "on":
                print("  测试连接...")
                result = await test_connection(mcp)
                print(f"  连接结果: {json.dumps(result, indent=4, ensure_ascii=False)}")
                results.append(result)
            print()

        return results


async def check_tool_status():
    """检查工具状态"""

    print("\n" + "=" * 80)
    print("2. 工具状态检查")
    print("=" * 80)

    async with async_session() as s:
        tools = (await s.execute(select(Tool))).scalars().all()

        if not tools:
            print("数据库中没有工具配置")
            return []

        print(f"\n找到 {len(tools)} 个工具:\n")

        for tool in tools:
            print(f"工具: {tool.name}")
            print(f"  类型: {tool.type}")
            print(f"  描述: {tool.description or '无'}")
            print(f"  启用: {tool.enabled}")

            if tool.params:
                print(f"  参数: {json.dumps(tool.params, indent=4, ensure_ascii=False)}")
            print()

        return tools


async def check_agent_tools():
    """检查 Agent 的工具挂载"""

    print("\n" + "=" * 80)
    print("3. Agent 工具挂载检查")
    print("=" * 80)

    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"

    async with async_session() as s:
        agent = (await s.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()

        if not agent:
            print(f"Agent {agent_id} 不存在")
            return

        print(f"\nAgent: {agent.name}")
        print(f"工具: {agent.tools or []}")
        print(f"MCP: {agent.mcps or []}")
        print(f"技能: {agent.skills or []}")
        print(f"文档: {agent.docs or []}")
        print(f"工作流: {agent.wfs or []}")


async def test_tool_execution():
    """测试工具执行"""

    print("\n" + "=" * 80)
    print("4. 工具执行测试")
    print("=" * 80)

    async with async_session() as s:
        tools = (await s.execute(select(Tool).where(Tool.enabled == True))).scalars().all()

        if not tools:
            print("没有启用的工具可测试")
            return

        # 测试第一个工具
        tool = tools[0]
        print(f"\n测试工具: {tool.name}")

        # 准备测试参数
        test_args = {}
        if tool.params:
            for p in tool.params:
                param_name = p.get('n', 'param')
                default = p.get('d')
                if default is not None:
                    test_args[param_name] = default

        print(f"参数: {test_args}")

        try:
            result = await execute_tool(str(tool.id), test_args)
            print(f"\n执行结果:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"\n执行失败: {e}")


async def main():
    """主检查流程"""

    try:
        await check_mcp_status()
        await check_tool_status()
        await check_agent_tools()
        await test_tool_execution()

        print("\n" + "=" * 80)
        print("检查完成")
        print("=" * 80)

    except Exception as e:
        print(f"\n检查失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
"""测试 MCP 工具动态执行。"""
import asyncio
import httpx
import json


async def test_mcp_tool():
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    base_url = "http://localhost:8000/api/v2"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Login
        login_response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test 1: 测试搜索功能（使用智能路由）
        print("=" * 60)
        print("测试 1: 使用 MCP 工具搜索 '长电 股价'")
        print("=" * 60)

        events = []
        async with client.stream(
            "POST",
            f"{base_url}/agents/{agent_id}/chat",
            headers=headers,
            json={"question": "Use MCP tool to search for '长电 股价'"}
        ) as response:
            async for line in response.aiter_lines():
                events.append(line)

        # 分析结果
        tool_starts = [e for e in events if "tool_start" in e]
        tool_ends = [e for e in events if "tool_end" in e]

        print(f"\n工具调用次数: {len(tool_starts)}")

        if tool_ends:
            print("\n工具返回内容（前500字符）:")
            # 提取工具返回
            for line in tool_ends:
                if "duckduckgo" in line.lower() or "search" in line.lower():
                    print(line[:500])
                    break

        # 检查是否有搜索结果
        events_str = str(events)
        has_results = any(keyword in events_str for keyword in [
            "股价", "stock", "长江电力", "600900", "价格", "price"
        ])

        print(f"\n{'✓ 包含搜索结果' if has_results else '✗ 无搜索结果'}")

        # 保存日志
        with open("mcp_tool_test.json", "w", encoding="utf-8") as f:
            json.dump({
                "events": events,
                "tool_starts": len(tool_starts),
                "tool_ends": len(tool_ends),
                "has_results": has_results
            }, f, ensure_ascii=False, indent=2)

        print("\n详细日志已保存到: mcp_tool_test.json")

        # Test 2: 直接测试工具执行
        print("\n" + "=" * 60)
        print("测试 2: 直接调用 MCP 工具")
        print("=" * 60)

        # 检查工具是否正确加载
        from app.core.agent.tool_registry_lazy import build_tools
        from app.models.agent import Agent
        from sqlalchemy import select
        from app.db.session import async_session

        async with async_session() as session:
            result = await session.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()

            if agent:
                tools = await build_tools(agent)
                mcp_tools = [t for t in tools if t.name.startswith("mcp_")]

                print(f"\n加载的 MCP 工具数量: {len(mcp_tools)}")
                for t in mcp_tools:
                    print(f"  - {t.name}")
                    print(f"    描述: {t.description[:100]}")

                    # 测试工具执行
                    print(f"\n  测试执行:")
                    try:
                        # 测试搜索功能
                        test_result = await t.ainvoke({
                            "tool_name": "",
                            "arguments": {"query": "长电 股价"}
                        })
                        print(f"    结果（前200字符）: {test_result[:200]}")

                        # 检查是否是真实的搜索结果
                        if "已就绪" in test_result or "包含" in test_result:
                            print(f"    ✗ 仍然返回占位符信息")
                        elif "股价" in test_result or "stock" in test_result.lower():
                            print(f"    ✓ 返回了真实的搜索结果")
                        else:
                            print(f"    ? 返回了其他内容")

                    except Exception as e:
                        print(f"    ✗ 执行失败: {str(e)}")


asyncio.run(test_mcp_tool())
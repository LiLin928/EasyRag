"""测试 MCP 工具执行（简化版）。"""
import asyncio
import httpx


async def test():
    base_url = "http://localhost:8000/api/v2"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Login
        login_response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get agent tools
        agent_response = await client.get(
            f"{base_url}/agents/545d7c33-0a98-4af6-afc3-f73b0f282efb",
            headers=headers
        )
        agent_data = agent_response.json()

        print(f"Agent: {agent_data['data']['name']}")
        print(f"MCPs: {agent_data['data']['mcps']}")

        # Get MCP config
        if agent_data['data']['mcps']:
            mcp_id = agent_data['data']['mcps'][0]
            mcp_response = await client.get(
                f"{base_url}/mcps/{mcp_id}",
                headers=headers
            )
            mcp_data = mcp_response.json()

            print(f"\nMCP: {mcp_data['data']['name']}")
            print(f"Status: {mcp_data['data']['status']}")
            print(f"Tool count: {mcp_data['data']['toolCount']}")

        # Test direct tool execution
        print("\n" + "="*60)
        print("Testing MCP tool execution:")
        print("="*60)

        # Load tools
        from app.core.agent.tool_registry_lazy import build_tools
        from app.models.agent import Agent
        from sqlalchemy import select
        from app.db.session import async_session

        async with async_session() as session:
            result = await session.execute(
                select(Agent).where(Agent.id == '545d7c33-0a98-4af6-afc3-f73b0f282efb')
            )
            agent = result.scalar_one_or_none()
            tools = await build_tools(agent)

            for tool in tools:
                if 'duckduckgo' in tool.name.lower():
                    print(f"\nTool: {tool.name}")

                    # Test 1: 使用智能路由
                    print("\nTest 1: 智能路由（自动选择工具）")
                    result1 = await tool.ainvoke({
                        'tool_name': '',
                        'arguments': {'query': '长电 股价'}
                    })
                    print(f"Result: {result1[:300]}")

                    # Test 2: 指定工具名
                    print("\nTest 2: 指定工具名称")
                    result2 = await tool.ainvoke({
                        'tool_name': 'search',
                        'arguments': {'query': '长江电力'}
                    })
                    print(f"Result: {result2[:300]}")

                    # Check if it's real results
                    if "search results" in result1 or "Found" in result1:
                        print("\n[SUCCESS] Tool returned real search results!")
                    else:
                        print("\n[FAILED] Tool did not return search results")


asyncio.run(test())
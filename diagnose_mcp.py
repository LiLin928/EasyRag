import httpx
import asyncio
import json

async def diagnose():
    base_url = "http://localhost:8000/api/v2"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Login
        login_response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check agent config
        agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
        agent_response = await client.get(
            f"{base_url}/agents/{agent_id}",
            headers=headers
        )
        agent_data = agent_response.json()

        print(f"Agent ID: {agent_id}")
        print(f"Agent Name: {agent_data['data']['name']}")
        print(f"Tools: {len(agent_data['data']['tools'])}")
        print(f"Skills: {agent_data['data']['skills']}")
        print(f"MCPs: {agent_data['data']['mcps']}")

        # Check MCP config
        if agent_data['data']['mcps']:
            mcp_id = agent_data['data']['mcps'][0]
            mcp_response = await client.get(
                f"{base_url}/mcps/{mcp_id}",
                headers=headers
            )
            mcp_data = mcp_response.json()

            print(f"\nMCP Details:")
            print(f"  ID: {mcp_id}")
            print(f"  Name: {mcp_data['data']['name']}")
            print(f"  Status: {mcp_data['data']['status']}")
            print(f"  Tool Count: {mcp_data['data']['toolCount']}")
            print(f"  Config: {json.dumps(mcp_data['data']['config'], indent=2)}")

        # Test tool execution
        print("\n" + "="*60)
        print("Testing tool execution...")
        print("="*60)

        # Simple test
        test_query = "Search for 长江电力 using MCP tool"
        print(f"\nQuery: {test_query}")

        events = []
        async with client.stream(
            "POST",
            f"{base_url}/agents/{agent_id}/chat",
            headers=headers,
            json={"question": test_query}
        ) as response:
            async for line in response.aiter_lines():
                events.append(line)

        # Analyze
        tool_calls = [e for e in events if "tool_start" in e or "tool_end" in e]
        print(f"\nTool events: {len(tool_calls)}")

        for event in tool_calls:
            if "tool_start" in event:
                print(f"\nTool Start: {event}")
            elif "tool_end" in event:
                print(f"\nTool End (first 500 chars): {event[:500]}")

                # Check if it's real data
                if "Found" in event or "search results" in event:
                    print("  -> Real search results detected!")
                elif "已就绪" in event or "包含" in event:
                    print("  -> Still returning placeholder!")

asyncio.run(diagnose())

import httpx
import asyncio

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

        # Test tool execution
        print("Testing MCP tool...")
        print("="*60)

        agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"

        events = []
        async with client.stream(
            "POST",
            f"{base_url}/agents/{agent_id}/chat",
            headers=headers,
            json={"question": "Use MCP tool to search '长江电力 股价'"}
        ) as response:
            async for line in response.aiter_lines():
                events.append(line)

        # Save events
        with open("mcp_events.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(events))

        # Analyze
        tool_starts = [e for e in events if "tool_start" in e]
        tool_ends = [e for e in events if "tool_end" in e]

        print(f"Tool starts: {len(tool_starts)}")
        print(f"Tool ends: {len(tool_ends)}")

        if tool_ends:
            print(f"\nTool end event:")
            print(tool_ends[0][:500])

        # Check result
        events_str = "\n".join(events)
        if "Found" in events_str or "search results" in events_str:
            print("\n[SUCCESS] Real search results!")
        elif "已就绪" in events_str or "包含" in events_str:
            print("\n[FAILED] Still returning placeholder!")
        else:
            print("\n[UNCERTAIN] Cannot determine")

asyncio.run(diagnose())

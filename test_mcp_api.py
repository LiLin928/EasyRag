import httpx
import asyncio

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

        # Test with explicit instruction
        print("Testing MCP tool with explicit instruction:")
        print("="*60)

        events = []
        async with client.stream(
            "POST",
            f"{base_url}/agents/545d7c33-0a98-4af6-afc3-f73b0f282efb/chat",
            headers=headers,
            json={"question": "Use the MCP duckduckgo-search tool. Tool name: search. Arguments: {\"query\": \"长江电力 股价\"}"}
        ) as response:
            async for line in response.aiter_lines():
                events.append(line)

        # Save and analyze
        with open("mcp_test_result.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(events))

        # Check results
        events_str = "\n".join(events)
        if "Found" in events_str or "search results" in events_str:
            print("[SUCCESS] Tool returned real search results!")
        else:
            print("[FAILED] Tool did not return search results")

        # Show tool output
        for line in events:
            if "tool_end" in line:
                print("\nTool output:")
                print(line[:500])
                break

asyncio.run(test())

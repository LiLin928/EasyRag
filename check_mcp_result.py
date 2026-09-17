import httpx
import asyncio
import json

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

        # Test MCP tool
        events = []
        async with client.stream(
            "POST",
            f"{base_url}/agents/545d7c33-0a98-4af6-afc3-f73b0f282efb/chat",
            headers=headers,
            json={"question": "Search 长电科技 using MCP"}
        ) as response:
            async for line in response.aiter_lines():
                events.append(line)

        # Save all events
        with open("mcp_all_events.json", "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)

        print(f"Saved {len(events)} events")

        # Find tool calls
        for idx, event in enumerate(events):
            if "tool_" in event:
                print(f"\nEvent {idx}: {event[:300]}")

asyncio.run(test())

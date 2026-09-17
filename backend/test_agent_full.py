import asyncio
import httpx
import json


async def test():
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

        # Test
        events = []
        async with client.stream(
            "POST",
            f"{base_url}/agents/{agent_id}/chat",
            headers=headers,
            json={"question": "Please calculate 1+200"}
        ) as response:
            async for line in response.aiter_lines():
                events.append(line)

        # Save all events
        with open("agent_events.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(events))
        
        print(f"Saved {len(events)} events to agent_events.txt")

        # Analyze tool calls
        tool_start = [e for e in events if "tool_start" in e]
        tool_end = [e for e in events if "tool_end" in e]
        
        print(f"\nTool starts: {len(tool_start)}")
        print(f"Tool ends: {len(tool_end)}")
        
        if tool_end:
            print("\nLast tool output:")
            print(tool_end[-1][:500])


asyncio.run(test())

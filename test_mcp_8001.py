import asyncio
import httpx

async def test():
    base_url = "http://localhost:8001/api/v2"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Login
        login_response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        print("Testing MCP tool on port 8001...")
        print("="*60)

        events = []
        async with client.stream(
            "POST",
            f"{base_url}/agents/545d7c33-0a98-4af6-afc3-f73b0f282efb/chat",
            headers=headers,
            json={"question": "Use MCP to search for 长电科技"}
        ) as response:
            async for line in response.aiter_lines():
                events.append(line)

        # Analyze
        events_str = "\n".join(events)
        
        # Check result
        if "Found" in events_str and "search results" in events_str:
            print("\n[SUCCESS] Real search results returned!")
            
            # Show first tool_end
            for event in events:
                if "tool_end" in event and len(event) > 100:
                    print(f"\nTool output (first 500 chars):")
                    print(event[:500])
                    break
        elif "已就绪" in events_str:
            print("\n[FAILED] Still returning placeholder")
        else:
            print("\n[UNCERTAIN] Result type unknown")

asyncio.run(test())

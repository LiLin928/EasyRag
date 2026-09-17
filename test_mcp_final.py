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

        # Test MCP tool
        print("Testing MCP tool execution...")
        print("="*60)

        events = []
        async with client.stream(
            "POST",
            f"{base_url}/agents/545d7c33-0a98-4af6-afc3-f73b0f282efb/chat",
            headers=headers,
            json={"question": "Use MCP tool to search for '长电科技 股票'"}
        ) as response:
            async for line in response.aiter_lines():
                events.append(line)

        # Analyze results
        events_str = "\n".join(events)
        
        # Check for real data
        if "Found" in events_str and "search results" in events_str:
            print("\n[SUCCESS] MCP tool returned real search results!")
            
            # Extract and show results
            for line in events:
                if "tool_end" in line:
                    # Save tool output
                    with open("mcp_result.txt", "w", encoding="utf-8") as f:
                        f.write(line)
                    print(f"\nTool output saved to mcp_result.txt")
                    print(f"First 500 chars: {line[:500]}")
                    break
                    
        elif "已就绪" in events_str:
            print("\n[FAILED] Still returning placeholder!")
        else:
            print("\n[UNCERTAIN] Cannot determine result type")

asyncio.run(test())

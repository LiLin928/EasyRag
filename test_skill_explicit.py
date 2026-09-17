import asyncio
import httpx


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

        # Test with explicit tool call request
        test_queries = [
            "Use the skill tool to calculate 1+200",  # 明确要求使用技能工具
            "Call the skill tool to add 1 and 200",   # 明确调用工具
            "Please use the skill_unnamed tool to compute 1+200",  # 明确指定工具名
        ]

        for query in test_queries:
            print(f"\n{'='*60}")
            print(f"Query: {query}")
            print('='*60)

            events = []
            async with client.stream(
                "POST",
                f"{base_url}/agents/{agent_id}/chat",
                headers=headers,
                json={"question": query}
            ) as response:
                async for line in response.aiter_lines():
                    events.append(line)

            # Check for tool calls
            tool_start = [e for e in events if "tool_start" in e]
            tool_end = [e for e in events if "tool_end" in e]

            print(f"Tool calls: {len(tool_start)}")

            if tool_end:
                print("\nTool output (first 500 chars):")
                print(tool_end[-1][:500])

            # Extract numbers from tokens
            import re
            tokens = []
            for line in events:
                if '"token"' in line:
                    match = re.search(r'"token":\s*"(.*?)"', line)
                    if match:
                        tokens.append(match.group(1))

            result = ''.join(tokens)
            print(f"\nAgent response: {result[:200]}")

            if "301" in result or any("301" in e for e in events):
                print("[SUCCESS] Found 301!")
            elif "201" in result:
                print("[FAILED] Still returning 201")


asyncio.run(test())

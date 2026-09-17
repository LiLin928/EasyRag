"""测试技能执行（简化版，避免编码问题）。"""
import asyncio
import httpx
import re


async def test_skill():
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    base_url = "http://localhost:8000/api/v2"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Login
        login_response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = login_response.json()["data"]["access_token"]
        print(f"[OK] Token obtained")

        # Test
        headers = {"Authorization": f"Bearer {token}"}
        full_response = []

        async with client.stream(
            "POST",
            f"{base_url}/agents/{agent_id}/chat",
            headers=headers,
            json={"question": "Calculate 1+200"}
        ) as response:
            async for line in response.aiter_lines():
                if "tool_start" in line or "tool_end" in line or "token" in line:
                    # Extract numbers from tokens
                    if '"token"' in line:
                        match = re.search(r'"token":\s*"(.*?)"', line)
                        if match:
                            token_value = match.group(1)
                            if re.search(r'\d+', token_value):
                                full_response.append(token_value)

        result = ''.join(full_response)
        print(f"\nAgent response: {result}")

        if "301" in result:
            print(f"[SUCCESS] Agent returned 301, skill script executed!")
        elif "201" in result:
            print(f"[FAILED] Agent returned 201, script not executed properly")
        else:
            print(f"[UNCERTAIN] No clear result found")


asyncio.run(test_skill())
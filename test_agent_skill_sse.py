"""测试智能体是否正确执行技能脚本（处理SSE流）。"""
import asyncio
import httpx
import json


async def test_agent_skill_execution():
    """测试智能体技能执行是否返回正确结果。"""

    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"  # 从日志中获取
    base_url = "http://localhost:8000/api/v2"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. 获取 token（使用 admin 登录）
        login_response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        login_data = login_response.json()

        if login_data.get("code") != 0:
            print(f"Login failed: {login_data}")
            return

        token = login_data["data"]["access_token"]
        print(f"[OK] Login successful, token obtained")

        # 2. 发送测试消息（SSE 流式响应）
        headers = {"Authorization": f"Bearer {token}"}

        # 测试 1+200（预期返回 301）
        test_query = "Use skill to calculate 1+200"
        print(f"\nSending test message: {test_query}")
        print(f"Expected result: 301 (1 + 200 + 100 bonus)")
        print(f"\nSSE Stream Output:")
        print("=" * 60)

        full_response = []

        async with client.stream(
            "POST",
            f"{base_url}/agents/{agent_id}/chat",
            headers=headers,
            json={"question": test_query}
        ) as response:
            async for line in response.aiter_lines():
                if line.strip():
                    print(line)
                    full_response.append(line)

        print("=" * 60)

        # 3. 分析结果
        response_text = "\n".join(full_response)
        print(f"\nAnalyzing response...")

        if "301" in response_text:
            print(f"[SUCCESS] Agent returned 301, skill script was executed!")
            print(f"✓ The script's +100 logic is working")
        elif "201" in response_text:
            print(f"[FAILED] Agent returned 201, skill script might not have been executed")
            print(f"✗ The +100 bonus was not applied")
        else:
            print(f"[UNCERTAIN] Cannot determine from response")

        # 4. 尝试提取具体的数字结果
        import re
        numbers = re.findall(r'\b\d{2,3}\b', response_text)
        if numbers:
            print(f"\nNumbers found in response: {numbers}")


if __name__ == "__main__":
    asyncio.run(test_agent_skill_execution())
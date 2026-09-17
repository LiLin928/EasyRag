"""测试智能体是否正确执行技能脚本。"""
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
            print(f"登录失败: {login_data}")
            return

        token = login_data["data"]["access_token"]
        print(f"[OK] Login successful, token obtained")

        # 2. Send test message
        headers = {"Authorization": f"Bearer {token}"}

        # Test 1+200 (expected: 301)
        test_query = "Use skill to calculate 1+200"
        print(f"\nSending test message: {test_query}")

        response = await client.post(
            f"{base_url}/agents/{agent_id}/chat",
            headers=headers,
            json={"message": test_query}
        )

        result = response.json()
        print(f"\n响应状态: {response.status_code}")
        print(f"响应内容: {json.dumps(result, ensure_ascii=False, indent=2)}")

        # 3. Check if result contains 301
        response_text = str(result)
        if "301" in response_text:
            print(f"\n[SUCCESS] Agent returned 301, skill script was executed!")
        elif "201" in response_text:
            print(f"\n[FAILED] Agent returned 201, skill script might not have been executed")
        else:
            print(f"\n[UNCERTAIN] Cannot determine, no obvious numbers in response")


if __name__ == "__main__":
    asyncio.run(test_agent_skill_execution())
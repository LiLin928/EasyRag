"""清除 Agent 历史记录脚本"""
import asyncio
import httpx


async def clear_agent_history():
    """清除 Agent 的历史记录"""

    base_url = "http://localhost:8000/api/v2"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. 登录
        print("=== 步骤1: 登录 ===")
        login_response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )

        if login_response.status_code != 200:
            print(f"[ERROR] 登录失败: {login_response.text}")
            return

        token = login_response.json()["data"]["access_token"]
        print(f"[OK] 登录成功，token: {token[:20]}...")

        # 2. 获取所有 Agent
        print("\n=== 步骤2: 获取 Agent 列表 ===")
        headers = {"Authorization": f"Bearer {token}"}

        agents_response = await client.get(
            f"{base_url}/agents",
            headers=headers
        )

        if agents_response.status_code != 200:
            print(f"[ERROR] 获取 Agent 列表失败: {agents_response.text}")
            return

        agents = agents_response.json()["data"]
        print(f"[OK] 找到 {len(agents)} 个 Agent:")
        for agent in agents:
            print(f"  - {agent['id']}: {agent['name']}")

        # 3. 清除每个 Agent 的历史
        print("\n=== 步骤3: 清除历史记录 ===")
        for agent in agents:
            agent_id = agent['id']
            agent_name = agent['name']

            print(f"\n清除 Agent '{agent_name}' 的历史...")
            clear_response = await client.delete(
                f"{base_url}/agents/{agent_id}/history",
                headers=headers
            )

            if clear_response.status_code == 200:
                result = clear_response.json()
                print(f"[OK] {result['data']['message']}")
            else:
                print(f"[ERROR] 清除失败: {clear_response.text}")

        print("\n=== 完成 ===")
        print("所有 Agent 的历史记录已清除")
        print("现在可以重新开始对话了")


if __name__ == "__main__":
    asyncio.run(clear_agent_history())
"""检查技能配置和脚本内容。"""
import asyncio
import httpx
import json


async def check_skill():
    base_url = "http://localhost:8000/api/v2"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Login
        login_response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get agent info
        agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
        agent_response = await client.get(
            f"{base_url}/agents/{agent_id}",
            headers=headers
        )
        agent_data = agent_response.json()

        print(f"Agent: {json.dumps(agent_data, ensure_ascii=False, indent=2)}")

        # Get skill info
        if agent_data.get("data", {}).get("skills"):
            skill_id = agent_data["data"]["skills"][0]
            skill_response = await client.get(
                f"{base_url}/skills/{skill_id}",
                headers=headers
            )
            skill_data = skill_response.json()

            print(f"\nSkill: {json.dumps(skill_data, ensure_ascii=False, indent=2)}")

            # Check scripts
            scripts = skill_data.get("data", {}).get("scripts", [])
            print(f"\nScripts count: {len(scripts)}")
            for idx, script in enumerate(scripts):
                print(f"\nScript {idx}:")
                print(f"  Name: {script.get('name')}")
                print(f"  Content length: {len(script.get('content', ''))}")
                if script.get('content'):
                    print(f"  Content preview: {script['content'][:200]}...")


asyncio.run(check_skill())

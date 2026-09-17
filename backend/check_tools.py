import asyncio
import httpx
import json


async def check():
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    base_url = "http://localhost:8000/api/v2"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Login
        login_response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get agent
        agent_response = await client.get(
            f"{base_url}/agents/{agent_id}",
            headers=headers
        )
        agent_data = agent_response.json()

        print("Agent configuration:")
        print(f"  Name: {agent_data['data']['name']}")
        print(f"  Model: {agent_data['data']['model']}")
        print(f"  Tools: {len(agent_data['data']['tools'])}")
        print(f"  Skills: {agent_data['data']['skills']}")
        print(f"  MCPs: {len(agent_data['data']['mcps'])}")

        # Check skill details
        if agent_data['data']['skills']:
            skill_id = agent_data['data']['skills'][0]
            skill_response = await client.get(
                f"{base_url}/skills/{skill_id}",
                headers=headers
            )
            skill_data = skill_response.json()

            print(f"\nSkill details:")
            print(f"  Name: {skill_data['data']['name']}")
            print(f"  Description: {skill_data['data']['description'][:100]}")
            print(f"  Scripts: {len(skill_data['data']['scripts'])}")


asyncio.run(check())

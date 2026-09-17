import asyncio
import httpx


async def check():
    base_url = "http://localhost:8000/api/v2"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Login
        login_response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get tool
        tool_id = "6b92349d-99a7-47f4-91d4-7006e37716b6"
        response = await client.get(
            f"{base_url}/tools/{tool_id}",
            headers=headers
        )
        tool_data = response.json()

        with open("weather_tool_config.json", "w", encoding="utf-8") as f:
            import json
            json.dump(tool_data, f, ensure_ascii=False, indent=2)

        print("Tool config saved to weather_tool_config.json")
        print(f"Tool name: {tool_data['data']['name']}")
        print(f"Tool type: {tool_data['data']['type']}")


asyncio.run(check())

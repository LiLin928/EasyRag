"""简单验证工具执行。"""
import asyncio
import httpx
import json


async def verify():
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

        # Test
        events = []
        async with client.stream(
            "POST",
            f"{base_url}/agents/{agent_id}/chat",
            headers=headers,
            json={"question": "Use tool to get Beijing weather"}
        ) as response:
            async for line in response.aiter_lines():
                events.append(line)

        # Save all events
        with open("weather_tool_log.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(events))

        # Analyze
        tool_starts = [e for e in events if "tool_start" in e]
        tool_ends = [e for e in events if "tool_end" in e]

        print(f"Total events: {len(events)}")
        print(f"Tool calls: {len(tool_starts)}")
        print(f"Tool returns: {len(tool_ends)}")

        if tool_ends:
            print("\nTool output (saved to weather_tool_log.txt):")
            print(f"First 500 chars of tool_end event:")
            print(tool_ends[-1][:500])

        # Check for real API data markers
        events_str = str(events)
        print("\n" + "="*60)
        print("验证真实API调用:")
        print("="*60)

        markers = {
            "温度数据": ["22.94", "24.94", "temperature"],
            "天气状况": ["scattered clouds", "多云"],
            "湿度": ["humidity", "60%"],
            "风速": ["wind", "2.39 m/s"],
            "气压": ["pressure", "1017"],
        }

        for name, keywords in markers.items():
            found = any(kw in events_str for kw in keywords)
            status = "[FOUND]" if found else "[NOT FOUND]"
            print(f"{status} {name}")


asyncio.run(verify())
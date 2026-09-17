"""验证工具执行的完整过程。"""
import asyncio
import httpx
import json
import re


async def verify_tool_execution():
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

        # Test query
        query = "使用工具告诉我北京今天的天气"
        print(f"发送查询: {query}\n")

        events = []
        async with client.stream(
            "POST",
            f"{base_url}/agents/{agent_id}/chat",
            headers=headers,
            json={"question": query}
        ) as response:
            async for line in response.aiter_lines():
                events.append(line)

        # 分析工具调用
        print("=" * 60)
        print("工具调用分析")
        print("=" * 60)

        tool_starts = [e for e in events if "tool_start" in e]
        tool_ends = [e for e in events if "tool_end" in e]

        print(f"\n工具调用次数: {len(tool_starts)}")

        if tool_starts:
            print("\n### 工具调用详情 ###")
            for idx, start in enumerate(tool_starts, 1):
                print(f"\n调用 {idx}:")
                # 提取工具名称和输入
                match = re.search(r'"tool":\s*"([^"]+)"', start)
                if match:
                    print(f"  工具名: {match.group(1)}")

                match = re.search(r'"input":\s*(\{[^}]+\})', start)
                if match:
                    print(f"  输入: {match.group(1)}")

        if tool_ends:
            print("\n### 工具返回详情 ###")
            for idx, end in enumerate(tool_ends, 1):
                print(f"\n返回 {idx}:")
                # 提取输出
                match = re.search(r'"output":\s*"([^"]{0,200})', end)
                if match:
                    output = match.group(1)
                    print(f"  输出预览: {output}...")

                # 检查关键信息
                if "北京" in end or "Beijing" in end:
                    print("  ✓ 包含北京相关信息")
                if "22.94" in end or "temperature" in end.lower():
                    print("  ✓ 包含温度数据")
                if "scattered clouds" in end.lower():
                    print("  ✓ 包含天气状况")

        # 提取最终响应
        print("\n" + "=" * 60)
        print("最终响应")
        print("=" * 60)

        tokens = []
        for line in events:
            if '"token"' in line:
                match = re.search(r'"token":\s*"(.*?)"', line)
                if match:
                    tokens.append(match.group(1))

        response_text = ''.join(tokens)
        print(f"\n{response_text[:500]}")

        # 验证关键数据点
        print("\n" + "=" * 60)
        print("数据验证")
        print("=" * 60)

        checks = [
            ("工具调用", len(tool_starts) > 0),
            ("工具返回", len(tool_ends) > 0),
            ("包含温度", "22.94" in str(events) or "温度" in response_text),
            ("包含天气", "多云" in response_text or "clouds" in str(events).lower()),
            ("包含湿度", "60%" in response_text or "humidity" in str(events).lower()),
        ]

        for check_name, result in checks:
            status = "✓ 通过" if result else "✗ 失败"
            print(f"{status} - {check_name}")

        # 保存详细日志
        with open("tool_execution_log.json", "w", encoding="utf-8") as f:
            json.dump({
                "query": query,
                "tool_starts": tool_starts,
                "tool_ends": tool_ends,
                "events": events,
                "response": response_text
            }, f, ensure_ascii=False, indent=2)

        print(f"\n详细日志已保存到: tool_execution_log.json")


asyncio.run(verify_tool_execution())
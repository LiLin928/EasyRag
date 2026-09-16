"""测试技能和 MCP 调用"""
import asyncio
import sys
import json
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService

async def test():
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    tests = [
        ("计算 1+100 是多少", "技能调用"),
        ("帮我搜索 今天长电的股票情况", "MCP 调用")
    ]

    svc = AgentService()

    for question, test_type in tests:
        print(f"\n{'='*60}")
        print(f"测试类型：{test_type}")
        print(f"问题：{question}")
        print('='*60)

        tool_calls = []
        response_text = ""
        has_error = False
        error_msg = ""

        async for event in svc.chat(agent_id, question, user_id):
            if event.startswith("event: "):
                lines = event.split("\n")
                event_type = lines[0].replace("event: ", "")
                event_data = lines[1].replace("data: ", "") if len(lines) > 1 else "{}"

                if event_type == "tool_start":
                    try:
                        data = json.loads(event_data)
                        tool_name = data.get("tool", "")
                        tool_input = data.get("input", "")
                        tool_calls.append(tool_name)
                        print(f"[工具调用] {tool_name}")
                        if tool_input:
                            print(f"[参数] {str(tool_input)[:200]}")
                    except:
                        pass
                elif event_type == "tool_end":
                    try:
                        data = json.loads(event_data)
                        output = data.get("output", "")
                        print(f"[工具返回] {str(output)[:200]}")
                    except:
                        pass
                elif event_type == "token":
                    try:
                        data = json.loads(event_data)
                        response_text += data.get("token", "")
                    except:
                        pass
                elif event_type == "error":
                    has_error = True
                    try:
                        data = json.loads(event_data)
                        error_msg = data.get("message", "")
                        print(f"[错误] {error_msg}")
                    except:
                        print(f"[错误] {event_data[:300]}")
                elif event_type == "done":
                    pass

        if has_error:
            print(f"\n状态：失败")
        elif tool_calls:
            print(f"\n状态：成功")
            print(f"使用的工具：{tool_calls}")
        else:
            print(f"\n状态：无工具调用")

if __name__ == "__main__":
    asyncio.run(test())
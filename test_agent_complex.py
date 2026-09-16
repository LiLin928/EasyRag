"""测试智能体复杂计算"""
import asyncio
import sys
import json
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService

async def test_complex():
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    questions = ["计算1+1", "计算123+456", "求 1.5 + 2.3 + 3.7 的和"]
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    svc = AgentService()

    for question in questions:
        tool_calls = []
        response_text = ""

        async for event in svc.chat(agent_id, question, user_id):
            if event.startswith("event: "):
                lines = event.split("\n")
                event_type = lines[0].replace("event: ", "")
                event_data = lines[1].replace("data: ", "") if len(lines) > 1 else "{}"

                if event_type == "tool_start":
                    try:
                        data = json.loads(event_data)
                        tool_calls.append(data.get("tool", ""))
                    except:
                        pass
                elif event_type == "token":
                    try:
                        data = json.loads(event_data)
                        response_text += data.get("token", "")
                    except:
                        pass

        print(f"\n问题：{question}")
        print(f"工具调用：{tool_calls if tool_calls else '无'}")
        print(f"回复长度：{len(response_text)} 字符")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(test_complex())
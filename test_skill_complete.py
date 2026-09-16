"""完整测试智能体技能功能"""
import asyncio
import sys
import json
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService

async def test_skill_complete():
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    questions = [
        "计算1+1",
        "帮我计算 1+100 是多少",
        "计算123+456",
        "求 1.5 + 2.3 + 3.7 的和"
    ]
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    svc = AgentService()

    for i, question in enumerate(questions, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}：{question}")
        print('='*60)

        tool_calls = []
        response_text = ""
        has_error = False

        async for event in svc.chat(agent_id, question, user_id):
            if event.startswith("event: "):
                lines = event.split("\n")
                event_type = lines[0].replace("event: ", "")
                event_data = lines[1].replace("data: ", "") if len(lines) > 1 else "{}"

                if event_type == "tool_start":
                    try:
                        data = json.loads(event_data)
                        tool_calls.append(data.get("tool", ""))
                        print(f"[工具调用] {data.get('tool', '')}")
                    except:
                        pass
                elif event_type == "token":
                    try:
                        data = json.loads(event_data)
                        token = data.get("token", "")
                        response_text += token
                    except:
                        pass
                elif event_type == "error":
                    has_error = True
                    try:
                        data = json.loads(event_data)
                        print(f"[错误] {data.get('message', '')}")
                    except:
                        pass
                elif event_type == "done":
                    pass

        if not has_error:
            print(f"\n回复：{response_text}")
            print(f"\n状态：成功")
            if tool_calls:
                print(f"技能已激活：{'是' if any('skill' in tc.lower() for tc in tool_calls) else '否'}")
        else:
            print(f"\n状态：失败")

if __name__ == "__main__":
    asyncio.run(test_skill_complete())
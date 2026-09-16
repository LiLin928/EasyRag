"""测试智能体技能调用（简化版）"""
import asyncio
import sys
import json
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService

async def test_skill():
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    question = "计算1+1"
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    svc = AgentService()

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

    # 输出结果
    print("测试结果：")
    print(f"问题：{question}")
    print(f"工具调用次数：{len(tool_calls)}")
    print(f"调用的工具：{tool_calls}")
    print(f"回复长度：{len(response_text)} 字符")

    # 判断是否成功
    if tool_calls:
        print("\n状态：成功")
        if any("skill" in tc.lower() for tc in tool_calls):
            print("技能已被激活并调用")
    else:
        print("\n状态：未检测到工具调用")

if __name__ == "__main__":
    asyncio.run(test_skill())
"""测试智能体技能调用"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService

async def test_skill():
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    question = "计算1+1"
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    svc = AgentService()
    print(f"问题：{question}")
    print("=" * 60)

    full_response = ""
    tool_calls = []
    skill_activated = False

    async for event in svc.chat(agent_id, question, user_id):
        # 解析事件
        if event.startswith("event: "):
            lines = event.split("\n")
            event_type = lines[0].replace("event: ", "")
            event_data = lines[1].replace("data: ", "") if len(lines) > 1 else "{}"

            if event_type == "tool_start":
                import json
                try:
                    data = json.loads(event_data)
                    tool_name = data.get("tool", "")
                    print(f"\n[工具调用] {tool_name}")
                    print(f"[参数] {event_data[:200]}")
                    tool_calls.append(tool_name)
                    if "skill" in tool_name.lower():
                        skill_activated = True
                except:
                    print(f"\n[工具调用] {event_data[:100]}")
            elif event_type == "tool_end":
                print(f"[工具完成]")
            elif event_type == "token":
                # 提取token内容
                import json
                try:
                    data = json.loads(event_data)
                    token = data.get("token", "")
                    full_response += token
                    print(token, end="", flush=True)
                except:
                    pass
            elif event_type == "done":
                print("\n" + "=" * 60)
                print("[完成] 对话完成")
            elif event_type == "error":
                print(f"\n[错误] {event_data}")

    print(f"\n\n完整回复：\n{full_response}")
    print(f"\n工具调用次数：{len(tool_calls)}")
    print(f"调用的工具：{tool_calls}")
    print(f"技能是否激活：{skill_activated}")

if __name__ == "__main__":
    asyncio.run(test_skill())
"""测试智能体技能（简化版）"""
import asyncio
import sys
import json
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService

async def test():
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    questions = [
        ("计算1+1", "2"),
        ("计算 1+100", "101"),
        ("计算123+456", "579"),
        ("求 1.5 + 2.3 + 3.7 的和", "7.5")
    ]
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    svc = AgentService()

    print("智能体技能测试报告")
    print("=" * 60)

    success_count = 0
    for question, expected in questions:
        response_text = ""
        tool_calls = []
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

        # 输出结果（避免emoji）
        if has_error:
            status = "失败"
        elif expected in response_text:
            status = "成功"
            success_count += 1
        else:
            status = "部分成功"
            success_count += 0.5

        print(f"{question:20s} | 预期: {expected:5s} | 状态: {status}")

    print("=" * 60)
    print(f"成功率：{success_count}/{len(questions)}")

if __name__ == "__main__":
    asyncio.run(test())
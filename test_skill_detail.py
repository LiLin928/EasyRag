"""详细测试技能脚本执行过程"""
import asyncio
import sys
import json
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService


async def test_skill_execution_detail():
    """测试技能脚本执行的详细过程"""
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    question = "计算 1+100"
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    print("=" * 60)
    print("详细测试技能脚本执行")
    print("=" * 60)

    svc = AgentService()

    async for event in svc.chat(agent_id, question, user_id):
        # 打印所有事件
        print(f"\n[EVENT] {event[:100]}...")

        if event.startswith("event: tool_start"):
            print("\n>>> 工具调用开始")
        elif event.startswith("event: tool_end"):
            print("\n>>> 工具调用结束")
            try:
                data = json.loads(event.split("data: ")[1])
                print(f"工具返回数据:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
            except Exception as e:
                print(f"解析失败: {e}")
        elif event.startswith("event: error"):
            print(f"\n>>> 错误: {event}")


if __name__ == "__main__":
    asyncio.run(test_skill_execution_detail())
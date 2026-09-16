"""测试技能调用 1+100"""
import asyncio
import sys
import json
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService

async def test_skill_error():
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    question = "帮我计算 1+100 是多少"
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    svc = AgentService()
    print(f"问题：{question}")
    print("=" * 60)

    async for event in svc.chat(agent_id, question, user_id):
        if event.startswith("event: "):
            lines = event.split("\n")
            event_type = lines[0].replace("event: ", "")
            event_data = lines[1].replace("data: ", "") if len(lines) > 1 else "{}"

            print(f"[{event_type}] {event_data[:300]}")

if __name__ == "__main__":
    asyncio.run(test_skill_error())
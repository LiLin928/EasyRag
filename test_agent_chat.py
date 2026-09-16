"""测试智能体对话功能"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService

async def test_agent_chat():
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"  # 测试2
    question = "今天北京天气怎么样"
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"  # admin

    svc = AgentService()
    print(f"开始测试智能体对话...")
    print(f"智能体 ID: {agent_id}")
    print(f"问题: {question}")
    print("-" * 50)

    event_count = 0
    try:
        async for event in svc.chat(agent_id, question, user_id):
            event_count += 1
            print(f"事件 {event_count}: {event[:200]}")  # 只打印前200字符

            # 如果是错误事件，打印完整信息
            if "error" in event:
                print(f"\n错误详情: {event}")
                break
    except Exception as e:
        print(f"\n异常: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

    print(f"\n总共收到 {event_count} 个事件")

if __name__ == "__main__":
    asyncio.run(test_agent_chat())
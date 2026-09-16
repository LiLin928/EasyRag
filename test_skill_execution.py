"""测试技能脚本执行"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService

async def test_skill_script():
    """测试技能脚本是否正确执行"""
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    question = "计算 1+100"
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    print("Test Skill Script Execution")
    print("=" * 60)
    print(f"Question: {question}")
    print("=" * 60)

    script_executed = False
    result_value = None

    svc = AgentService()

    async for event in svc.chat(agent_id, question, user_id):
        if event.startswith("event: tool_start"):
            print(f"[Tool Called] Skill activated")
        elif event.startswith("event: tool_end"):
            # Check if script result is in the output
            if "script" in event.lower() or "extract" in event.lower():
                script_executed = True
                print(f"[Script Executed] Script output detected")
                # Try to extract result
                import json
                try:
                    data = json.loads(event.split("data: ")[1])
                    if "output" in str(data):
                        result_value = data.get("output")
                except:
                    pass
        elif event.startswith("event: token"):
            pass
        elif event.startswith("event: error"):
            print(f"[Error] {event}")

    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)

    if script_executed:
        print("Script execution: YES")
        if result_value:
            print(f"Result: {result_value}")
            # Check if the result includes the +100
            if "201" in str(result_value) or (isinstance(result_value, (int, float)) and result_value == 201):
                print("Calculation correct: 1+100+100=201")
            else:
                print(f"Result value: {result_value}")
    else:
        print("Script execution: NO")
        print("Skills may not be working correctly")

if __name__ == "__main__":
    asyncio.run(test_skill_script())
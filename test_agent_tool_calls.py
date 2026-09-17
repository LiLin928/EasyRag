"""
测试 Agent 工具调用（完整流程）
"""
import asyncio
import sys
import json

sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService


async def test_agent_tool_calls():
    """测试 Agent 的工具、MCP、技能调用"""

    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    tests = [
        {
            "name": "测试1: 工具调用（天气查询）",
            "question": "北京今天天气怎么样",
            "expected_tool": "tool_",  # 工具名称前缀
        },
        {
            "name": "测试2: 技能调用（数字计算）",
            "question": "计算 1+100",
            "expected_tool": "skill_",  # 技能名称前缀
        },
        {
            "name": "测试3: MCP 调用（搜索）",
            "question": "帮我搜索长电科技的股票",
            "expected_tool": "search",  # MCP 工具名称
        },
    ]

    svc = AgentService()

    for test in tests:
        print("\n" + "=" * 80)
        print(test['name'])
        print("=" * 80)
        print(f"问题: {test['question']}")

        tool_called = False
        tool_name = None
        result_parts = []

        async for event in svc.chat(agent_id, test['question'], user_id):
            if event.startswith("event: tool_start"):
                tool_called = True
                import json
                try:
                    data = json.loads(event.split("data: ")[1])
                    tool_name = data.get("tool", "")
                    print(f"\n[工具调用] {tool_name}")
                except:
                    pass

            elif event.startswith("event: tool_end"):
                try:
                    data = json.loads(event.split("data: ")[1])
                    print(f"[工具输出] 成功: {data.get('output', {}).get('success', 'N/A')}")
                except:
                    pass

            elif event.startswith("event: token"):
                try:
                    token = event.split("data: ")[1].strip()
                    if token:
                        result_parts.append(token)
                except:
                    pass

        # 检查结果
        print(f"\n回答: {''.join(result_parts[:100])}...")

        if tool_called:
            print(f"[成功] 工具被调用: {tool_name}")
            if test['expected_tool'] in tool_name:
                print(f"[匹配] 符合预期工具类型: {test['expected_tool']}")
        else:
            print("[失败] 工具未被调用")


async def main():
    """主测试流程"""
    await test_agent_tool_calls()

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
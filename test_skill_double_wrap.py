"""测试技能脚本双重包装问题

问题：脚本被包装了两次，导致执行结果重复。
- skill_tool_executor.py 中的 _wrap_script_with_auto_call() 包装一次
- script_executor.py 中的 execute_skill_script() 又包装一次

修复方案：移除 skill_tool_executor.py 中的包装，让 script_executor.py 统一处理。
"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService


async def test_skill_double_wrap():
    """测试技能脚本是否被双重包装"""
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    question = "计算 1+100"
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    print("=" * 60)
    print("测试技能脚本双重包装问题")
    print("=" * 60)
    print(f"问题：{question}")
    print(f"预期：如果脚本有 +100，应该只加一次（结果 201）")
    print(f"如果双重执行：结果会是 301（加了两次）")
    print("=" * 60)

    result_parts = []
    tool_output = None

    svc = AgentService()

    async for event in svc.chat(agent_id, question, user_id):
        if event.startswith("event: tool_start"):
            print("\n[工具调用] 技能已激活")
        elif event.startswith("event: tool_end"):
            import json
            try:
                data = json.loads(event.split("data: ")[1])
                if "output" in str(data):
                    tool_output = data.get("output", "")
                    print(f"\n[工具输出]\n{tool_output}")
            except:
                pass
        elif event.startswith("event: token"):
            # 提取 token 内容
            try:
                token = event.split("data: ")[1].strip()
                if token:
                    result_parts.append(token)
            except:
                pass
        elif event.startswith("event: error"):
            print(f"\n[错误] {event}")

    # 分析结果
    print("\n" + "=" * 60)
    print("最终回答")
    print("=" * 60)
    final_answer = "".join(result_parts)
    print(final_answer)

    # 检查是否双重执行
    print("\n" + "=" * 60)
    print("问题诊断")
    print("=" * 60)

    if "201" in final_answer or "201" in str(tool_output):
        print("✅ 正确：脚本执行一次，结果为 201")
    elif "301" in final_answer or "301" in str(tool_output):
        print("❌ 错误：脚本被执行两次，结果为 301")
        print("   → 双重包装问题：脚本在 skill_tool_executor.py 和 script_executor.py 都被包装")
    elif "101" in final_answer:
        print("⚠️  脚本未生效：结果为 101，说明 +100 的逻辑未执行")

    print("\n" + "=" * 60)
    print("建议修复")
    print("=" * 60)
    print("移除 skill_tool_executor.py 中的 _wrap_script_with_auto_call() 函数")
    print("让 script_executor.py 统一处理脚本包装和执行")


if __name__ == "__main__":
    asyncio.run(test_skill_double_wrap())
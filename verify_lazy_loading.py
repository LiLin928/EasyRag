"""验证延迟加载效果"""
import asyncio
import sys
import time
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService

async def test_lazy_loading():
    """测试延迟加载是否生效"""
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    question = "北京今天天气怎么样"
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    print("测试延迟加载效果")
    print("=" * 60)
    print(f"智能体ID: {agent_id}")
    print(f"问题: {question}")
    print("=" * 60)

    start_time = time.time()
    tool_count = 0
    mcp_proxy_count = 0

    svc = AgentService()

    async for event in svc.chat(agent_id, question, user_id):
        if event.startswith("event: tool_start"):
            tool_count += 1
            # 检查是否是 MCP 代理工具
            if "mcp_proxy" in event or "mcp_" in event:
                mcp_proxy_count += 1
                print(f"✓ MCP 代理工具被调用")

    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)
    print(f"总工具调用次数: {tool_count}")
    print(f"MCP 代理工具次数: {mcp_proxy_count}")
    print(f"总耗时: {elapsed:.2f}s")

    if mcp_proxy_count > 0:
        print("\n✅ 延迟加载已生效：MCP 工具按需加载")
    else:
        print("\n⚠️  未检测到 MCP 代理工具")

if __name__ == "__main__":
    asyncio.run(test_lazy_loading())
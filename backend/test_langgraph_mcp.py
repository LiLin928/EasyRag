"""测试 LangGraph 如何处理 MCP 工具调用"""
import asyncio
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from app.db.session import async_session
from app.models.agent import Agent
from app.core.agent.tool_registry_lazy import build_tools


async def test_langgraph_mcp():
    """测试 LangGraph Agent 如何处理 MCP 工具"""

    print("=== 测试 LangGraph + MCP 工具 ===\n")

    # 1. 获取 Agent 配置
    async with async_session() as s:
        agent = (await s.execute(select(Agent).where(Agent.name == '测试2'))).scalar_one_or_none()
        if not agent:
            print("没有找到测试 Agent")
            return

        print(f"Agent: {agent.name}")
        print(f"MCPs: {agent.mcps}\n")

        # 2. 构建工具列表
        print("构建工具列表...")
        tools = await build_tools(agent, lazy_mcp=True)
        print(f"工具数量: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:50]}...")

        print("\n工具名称列表:", [t.name for t in tools])

        # 3. 创建 LLM
        from app.providers.langchain_factory import build_chat_model
        llm = await build_chat_model(use="qa", temperature=0.7)

        # 4. 创建 React Agent
        print("\n创建 React Agent...")
        try:
            react = create_react_agent(
                model=llm,
                tools=tools,
            )
            print("[OK] React Agent 创建成功")
        except Exception as e:
            print(f"[ERROR] 创建失败: {e}")
            import traceback
            print(traceback.format_exc())
            return

        # 5. 测试对话
        print("\n=== 测试对话 ===")
        config = {"configurable": {"thread_id": "test_thread_123"}}
        messages = [HumanMessage(content="使用MCP帮我搜索今天的新闻")]

        print(f"发送消息: {messages[0].content}\n")

        try:
            print("开始执行...")
            event_count = 0
            tool_calls = []
            tool_messages = []

            async for event in react.astream_events({"messages": messages}, config=config, version="v2"):
                event_count += 1
                kind = event["event"]
                name = event.get("name", "")

                if kind == "on_tool_start":
                    print(f"\n[Tool Start] {name}")
                    input_data = event["data"].get("input", {})
                    print(f"  输入: {input_data}")
                    tool_calls.append({"name": name, "input": input_data})

                elif kind == "on_tool_end":
                    print(f"\n[Tool End] {name}")
                    output = event["data"].get("output", "")
                    print(f"  输出长度: {len(str(output))}")
                    tool_messages.append({"name": name, "output": output})

                elif kind == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    content = getattr(chunk, "content", "") if chunk else ""
                    if content:
                        print(f"[Token] {content}", end="", flush=True)

                elif kind == "on_chain_error":
                    print(f"\n[ERROR] Chain error: {event['data']}")

            print(f"\n\n=== 执行统计 ===")
            print(f"总事件数: {event_count}")
            print(f"工具调用: {len(tool_calls)}")
            print(f"工具响应: {len(tool_messages)}")

            if len(tool_calls) > 0 and len(tool_messages) == 0:
                print("\n[CRITICAL] 检测到问题：")
                print("  - 有工具调用但没有工具响应！")
                print("  - 这会导致 'Found AIMessages with tool_calls that do not have a corresponding ToolMessage' 错误")
                print("\n失败的调用:")
                for tc in tool_calls:
                    print(f"  - {tc['name']}: {tc['input']}")
            elif len(tool_calls) == len(tool_messages):
                print("\n[OK] 工具调用和响应数量匹配")

        except Exception as e:
            print(f"\n[ERROR] 执行失败: {e}")
            import traceback
            print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(test_langgraph_mcp())
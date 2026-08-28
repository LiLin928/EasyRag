"""Agent 服务：create_react_agent + astream_events SSE 流式。

SSE 事件对齐前端 types/agent.ts：
phase / tool_start / tool_end / token / done / error。
"""
from typing import AsyncIterator

from sqlalchemy import select

from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.agent import Agent
from app.providers.langchain_factory import build_chat_model
from app.sse.emitter import sse_event


class AgentService:
    """智能体对话服务。"""

    async def chat(self, agent_id: str, question: str, user_id) -> AsyncIterator[str]:
        """流式执行 agent 对话，yield SSE 事件。"""
        async with async_session() as s:
            agent = (await s.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
        if not agent or not agent.enabled:
            yield sse_event("error", {"code": 40300, "message": "智能体不存在或未启用"})
            return

        try:
            from langgraph.prebuilt import create_react_agent

            from app.core.agent.memory import get_checkpointer
            from app.core.agent.tool_registry import build_tools

            llm = await build_chat_model(use="qa", temperature=agent.temp)
            tools = await build_tools(agent)
            react = create_react_agent(
                model=llm,
                tools=tools,
                state_modifier=agent.prompt or "",
                checkpointer=await get_checkpointer(),
            )
        except Exception as e:
            yield sse_event("error", {"code": 50001, "message": f"智能体初始化失败: {e}"})
            return

        config = {"configurable": {"thread_id": f"agent:{agent_id}:{user_id}"}}
        yield sse_event("phase", {"phase": "generate", "message": f"智能体 {agent.name} 思考中..."})

        try:
            async for ev in react.astream_events(
                {"messages": [("user", question)]}, config=config, version="v2"
            ):
                kind = ev["event"]
                name = ev.get("name", "")
                if kind == "on_tool_start":
                    yield sse_event("tool_start", {"tool": name, "input": str(ev["data"].get("input", ""))[:200]})
                elif kind == "on_tool_end":
                    yield sse_event("tool_end", {"tool": name, "output": str(ev["data"].get("output", ""))[:500]})
                elif kind == "on_chat_model_stream":
                    token = ev["data"].get("chunk")
                    content = getattr(token, "content", "") if token else ""
                    if content:
                        yield sse_event("token", {"token": content})
        except Exception as e:
            yield sse_event("error", {"code": 50001, "message": str(e)})
            return

        # 更新 last_active
        from datetime import datetime
        async with async_session() as s:
            a = (await s.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
            if a:
                a.last_active = datetime.now()
                await s.commit()

        yield sse_event("done", {"agentId": agent_id})
 

"""Agent 服务：create_react_agent + astream_events SSE 流式。

SSE 事件对齐前端 types/agent.ts：
phase / tool_start / tool_end / token / done / error。
"""
from typing import AsyncIterator

from sqlalchemy import select

from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.agent import Agent
from app.providers.langchain_factory import build_chat_model_by_name
from app.sse.emitter import sse_event


class AgentService:
    """智能体对话服务。"""

    async def chat(self, agent_id: str, question: str, user_id) -> AsyncIterator[str]:
        """流式执行 agent 对话，yield SSE 事件。"""
        import logging
        logger = logging.getLogger(__name__)

        async with async_session() as s:
            agent = (await s.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
        if not agent or not agent.enabled:
            yield sse_event("error", {"code": 40300, "message": "智能体不存在或未启用"})
            return

        logger.info(f"[Agent] Starting chat for agent {agent.name}, prompt: {agent.prompt[:50] if agent.prompt else 'None'}...")

        try:
            from langgraph.prebuilt import create_react_agent

            from app.core.agent.memory import get_checkpointer
            from app.core.agent.tool_registry import build_tools

            # 使用 Agent 配置的模型，而非全局默认模型
            llm = await build_chat_model_by_name(
                model_name=agent.model,
                temperature=agent.temp,
                max_tokens=int(agent.maxtok) if agent.maxtok else None
            )
            tools = await build_tools(agent)
            logger.info(f"[Agent] Agent {agent.name} initialized with {len(tools)} tools")

            # 构造系统提示词
            from langchain_core.messages import SystemMessage
            system_prompt = None
            if agent.prompt:
                system_prompt = SystemMessage(content=agent.prompt)
                logger.info(f"[Agent] System prompt set: {agent.prompt[:100]}...")

            react = create_react_agent(
                model=llm,
                tools=tools,
                prompt=system_prompt,  # 传递 SystemMessage 对象
                checkpointer=await get_checkpointer(),
            )
            logger.info(f"[Agent] React agent created successfully")
        except Exception as e:
            yield sse_event("error", {"code": 50001, "message": f"智能体初始化失败: {e}"})
            return

        config = {"configurable": {"thread_id": f"agent:{agent_id}:{user_id}"}}
        yield sse_event("phase", {"phase": "generate", "message": f"智能体 {agent.name} 思考中..."})

        # 检查是否有历史状态
        current_state = await react.aget_state(config)
        if current_state and current_state.values.get("messages"):
            history_count = len(current_state.values["messages"])
            logger.info(f"[Agent] Loaded {history_count} messages from checkpointer history")
        else:
            logger.info("[Agent] No history found, starting fresh conversation")

        # 构造消息列表（不需要包含系统提示词，已通过 prompt 参数设置）
        messages = [{"role": "user", "content": question}]
        logger.info(f"[Agent] User question: {question}")

        try:
            async for ev in react.astream_events(
                {"messages": messages}, config=config, version="v2"
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
 

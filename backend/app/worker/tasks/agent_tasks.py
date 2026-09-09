"""Agent Celery 任务"""
import asyncio
from typing import Dict, Any, Optional
from celery.exceptions import MaxRetriesExceededError
import logging

from app.core.celery_app import celery_app
from app.core.redis_streams import publish_event

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, time_limit=1800)
def execute_agent_chat(
    self,
    agent_id: str,
    chat_id: str,
    question: str,
    conversation_id: Optional[str] = None,
    **kwargs
) -> dict:
    """
    Agent 对话任务
    
    长时间运行任务，支持流式输出
    
    Args:
        agent_id: Agent ID
        chat_id: 聊天 ID (用于 SSE 流)
        question: 用户问题
        conversation_id: 会话 ID (可选)
        
    Returns:
        对话结果
    """
    stream_key = f"agent:{chat_id}"
    
    try:
        # 1. 发送开始事件
        _publish_sync(stream_key, "phase", {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "phase": "thinking",
            "question": question
        })
        
        # 2. 构建 Agent (模拟)
        # TODO: 实际调用 AgentService
        # from app.services.agent_service import AgentService
        # agent_service = AgentService()
        
        # 3. 模拟流式输出
        # 实际应该使用 LangChain 的 astream_events
        _publish_sync(stream_key, "token", {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "token": "",
            "is_start": True
        })
        
        # 模拟 token 流
        response = ""
        tokens = ["我", "是", "Agent", "，", "正在", "回答", "您", "的", "问题", "。"]
        for token in tokens:
            response += token
            _publish_sync(stream_key, "token", {
                "agent_id": agent_id,
                "chat_id": chat_id,
                "token": token,
                "is_start": False
            })
            # 模拟延迟
            import time
            time.sleep(0.1)
        
        # 4. 模拟工具调用
        _publish_sync(stream_key, "tool_start", {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "tool": "search_knowledge",
            "input": {"query": question}
        })
        
        # 模拟工具执行
        import time
        time.sleep(0.5)
        
        _publish_sync(stream_key, "tool_end", {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "tool": "search_knowledge",
            "output": {"chunks": 3, "sources": []}
        })
        
        # 5. 完成
        result = {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "conversation_id": conversation_id,
            "question": question,
            "answer": response + " (这是示例回答)",
            "tokens_used": len(tokens) + 100,
            "tools_used": ["search_knowledge"]
        }
        
        _publish_sync(stream_key, "done", {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "result": result
        })
        
        logger.info(f"Agent chat completed: agent_id={agent_id}, chat_id={chat_id}")
        return result
        
    except Exception as exc:
        logger.error(f"Agent chat failed: agent_id={agent_id}, chat_id={chat_id}, error={exc}")
        
        _publish_sync(stream_key, "error", {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "error": str(exc)
        })
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        
        raise


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def execute_agent_tool(
    self,
    agent_id: str,
    chat_id: str,
    tool_name: str,
    tool_input: Dict[str, Any]
) -> dict:
    """
    执行 Agent 工具
    
    用于独立工具执行任务
    
    Args:
        agent_id: Agent ID
        chat_id: 聊天 ID
        tool_name: 工具名称
        tool_input: 工具输入
        
    Returns:
        工具执行结果
    """
    stream_key = f"agent:{chat_id}"
    
    try:
        _publish_sync(stream_key, "tool_start", {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "tool": tool_name,
            "input": tool_input
        })
        
        # TODO: 调用实际工具
        # from app.services.tool_service import execute_tool
        # result = execute_tool(tool_name, tool_input)
        
        import time
        time.sleep(0.5)
        
        result = {"status": "success", "output": f"Tool {tool_name} executed"}
        
        _publish_sync(stream_key, "tool_end", {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "tool": tool_name,
            "output": result
        })
        
        return result
        
    except Exception as exc:
        logger.error(f"Tool execution failed: {tool_name}, error={exc}")
        
        _publish_sync(stream_key, "tool_end", {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "tool": tool_name,
            "error": str(exc)
        })
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        
        raise


def _publish_sync(stream: str, event_type: str, payload: dict):
    """同步发布事件"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(publish_event(stream, event_type, payload))
        loop.close()
    except Exception as e:
        logger.warning(f"Failed to publish event: {e}")

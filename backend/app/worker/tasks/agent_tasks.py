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

    使用 AgentService 执行对话，通过 Redis Streams 推送 SSE 事件

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
        # 创建事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 执行 Agent 对话
            result = loop.run_until_complete(
                _execute_agent_chat_async(
                    agent_id, chat_id, question, conversation_id, stream_key
                )
            )
            return result
        finally:
            loop.close()

    except Exception as exc:
        logger.error(f"Agent chat failed: agent_id={agent_id}, error={exc}")

        _publish_sync(stream_key, "error", {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "error": str(exc)
        })

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)

        raise


async def _execute_agent_chat_async(
    agent_id: str,
    chat_id: str,
    question: str,
    conversation_id: Optional[str],
    stream_key: str
) -> dict:
    """异步执行 Agent 对话"""
    from app.services.agent_service import AgentService
    from app.db.session import async_session
    from sqlalchemy import select
    from app.models.agent import Agent

    # 获取 agent 信息
    async with async_session() as session:
        agent = (await session.execute(
            select(Agent).where(Agent.id == agent_id)
        )).scalar_one_or_none()

        if not agent:
            _publish_sync(stream_key, "error", {
                "code": 40300,
                "message": "智能体不存在"
            })
            return {"status": "failed", "error": "Agent not found"}

        user_id = agent.user_id

    # 调用 AgentService
    svc = AgentService()
    full_response = ""

    try:
        async for event in svc.chat(agent_id, question, user_id):
            # 解析 SSE 事件并转发到 Redis Streams
            if event.startswith("data:"):
                import json
                try:
                    data = json.loads(event[5:].strip())
                    event_type = data.get("event", "unknown")

                    # 转发事件
                    _publish_sync(stream_key, event_type, data)

                    # 收集响应
                    if event_type == "token":
                        full_response += data.get("token", "")
                except json.JSONDecodeError:
                    pass

        logger.info(f"Agent chat completed: agent_id={agent_id}, chat_id={chat_id}")
        return {
            "agent_id": agent_id,
            "chat_id": chat_id,
            "status": "success",
            "response_length": len(full_response)
        }

    except Exception as exc:
        logger.error(f"Agent chat async failed: {exc}")
        _publish_sync(stream_key, "error", {
            "code": 50001,
            "message": str(exc)
        })
        raise


def _publish_sync(stream: str, event_type: str, payload: dict):
    """同步发布事件到 Redis Streams"""
    try:
        import redis
        import json
        from datetime import datetime
        import os

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        r = redis.from_url(redis_url)

        data = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": json.dumps(payload),
        }

        r.xadd(stream, data, maxlen=10000, approximate=True)
        logger.debug(f"Published event: {event_type} to {stream}")
    except Exception as e:
        logger.warning(f"Failed to publish event: {e}")
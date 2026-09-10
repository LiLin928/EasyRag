"""工作流 Celery 任务

使用 LangGraph 执行工作流定义。
"""
import asyncio
from typing import List, Dict, Any
from celery import chain, group, chord
from celery.exceptions import MaxRetriesExceededError
import logging

from app.core.celery_app import celery_app
from app.core.redis_streams import publish_event

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def execute_workflow(self, execution_id: str, definition: Dict[str, Any], debug: bool = False) -> dict:
    """
    工作流执行任务

    使用 LangGraph StateGraph 执行工作流

    Args:
        execution_id: 执行 ID
        definition: 工作流定义 {nodes: [...], edges: [...]}
        debug: 是否调试模式

    Returns:
        执行结果
    """
    stream_key = f"workflow:{execution_id}"

    try:
        # 创建事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 执行工作流
            result = loop.run_until_complete(
                _execute_workflow_async(execution_id, definition, debug, stream_key)
            )
            return result
        finally:
            loop.close()

    except Exception as exc:
        logger.error(f"Workflow execution failed: {execution_id}, error={exc}")

        _publish_sync(stream_key, "execution_failed", {
            "execution_id": execution_id,
            "error": str(exc)
        })

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)

        raise


async def _execute_workflow_async(
    execution_id: str,
    definition: Dict[str, Any],
    debug: bool,
    stream_key: str
) -> dict:
    """异步执行工作流"""
    # 1. 发送开始事件
    _publish_sync(stream_key, "execution_started", {
        "execution_id": execution_id,
        "debug": debug
    })

    nodes = definition.get("nodes", [])
    edges = definition.get("edges", [])

    if not nodes:
        raise ValueError("Workflow definition has no nodes")

    # 2. 使用 GraphBuilder 构建 LangGraph
    from app.core.engine.graph_builder import GraphBuilder
    from app.core.engine.state import WorkflowState

    builder = GraphBuilder()
    graph = await builder.build(definition, execution_id, debug)

    # 3. 准备初始状态
    initial_state = {
        "execution_id": execution_id,
        "workflow_id": "",  # 从上下文获取
        "inputs": {},
        "variables": {},
        "node_outputs": {},
        "node_timings": {},
        "current_node": None,
        "status": "running",
    }

    # 4. 执行工作流
    try:
        config = {"configurable": {"thread_id": execution_id}}

        async for event in graph.astream_events(initial_state, config=config, version="v2"):
            kind = event.get("event")
            name = event.get("name", "")
            data = event.get("data", {})

            # 发布节点事件
            if kind == "on_chain_start":
                _publish_sync(stream_key, "node_started", {
                    "execution_id": execution_id,
                    "node_id": name,
                })
            elif kind == "on_chain_end":
                _publish_sync(stream_key, "node_completed", {
                    "execution_id": execution_id,
                    "node_id": name,
                    "output": str(data.get("output", ""))[:500],
                })

        # 5. 获取最终状态
        final_state = await graph.aget_state(config)

        result = {
            "execution_id": execution_id,
            "status": "completed",
            "final_state": {
                "node_outputs": final_state.values.get("node_outputs", {}),
                "status": final_state.values.get("status", "completed"),
            }
        }

        _publish_sync(stream_key, "execution_completed", {
            "execution_id": execution_id,
            "result": result
        })

        logger.info(f"Workflow execution completed: {execution_id}")
        return result

    except Exception as exc:
        logger.error(f"Workflow async execution failed: {exc}")
        _publish_sync(stream_key, "execution_failed", {
            "execution_id": execution_id,
            "error": str(exc)
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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def execute_node_task(self, execution_id: str, node: Dict[str, Any]) -> dict:
    """
    执行单个工作流节点（用于调试或手动执行）

    Args:
        execution_id: 执行 ID
        node: 节点定义

    Returns:
        节点执行结果
    """
    stream_key = f"workflow:{execution_id}"

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                _execute_node_async(execution_id, node, stream_key)
            )
            return result
        finally:
            loop.close()

    except Exception as exc:
        logger.error(f"Node execution failed: {node.get('id')}, error={exc}")
        raise self.retry(exc=exc, countdown=30)


async def _execute_node_async(execution_id: str, node: Dict[str, Any], stream_key: str) -> dict:
    """异步执行单个节点"""
    from app.core.engine.nodes.base import NodeRouter

    # 创建节点执行器
    executor = NodeRouter.create(node)

    # 准备状态
    state = {
        "execution_id": execution_id,
        "node_outputs": {},
        "variables": {},
    }

    # 执行节点
    _publish_sync(stream_key, "node_started", {
        "execution_id": execution_id,
        "node_id": node["id"],
        "node_type": node["type"],
    })

    result = await executor.run(state)

    _publish_sync(stream_key, "node_completed", {
        "execution_id": execution_id,
        "node_id": node["id"],
        "result": result,
    })

    return result
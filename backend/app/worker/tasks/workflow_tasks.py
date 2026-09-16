"""工作流 Celery 任务

使用 LangGraph 执行工作流定义。
"""
import asyncio
from typing import List, Dict, Any
from celery import chain, group, chord
from celery.exceptions import MaxRetriesExceededError
import structlog

from app.core.celery_app import celery_app
from app.core.redis_streams import publish_event

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="execute_workflow"  # 显式任务名称，确保与调用一致
)
def execute_workflow(
    self,
    execution_id: str,
    definition: Dict[str, Any],
    inputs: Dict[str, Any] = None,
    debug: bool = False
) -> dict:
    """
    工作流执行任务

    使用 LangGraph StateGraph 执行工作流

    Args:
        execution_id: 执行 ID
        definition: 工作流定义 {nodes, edges}
        inputs: 工作流输入参数
        debug: 是否调试模式
        definition: 工作流定义 {nodes: [...], edges: [...]}
        debug: 是否调试模式

    Returns:
        执行结果
    """
    logger.info(f"[Workflow] Task started", execution_id=execution_id, debug=debug, inputs=inputs)
    stream_key = f"workflow:{execution_id}"

    try:
        # Windows 兼容性：设置事件循环策略
        import sys
        if sys.platform == 'win32':
            from asyncio import WindowsSelectorEventLoopPolicy
            asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

        # 创建事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 执行工作流
            result = loop.run_until_complete(
                _execute_workflow_async(execution_id, definition, inputs or {}, debug, stream_key)
            )
            return result
        finally:
            # 清理：关闭事件循环
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    except Exception as exc:
        logger.error(f"Workflow execution failed: {execution_id}, error={exc}")

        _publish_sync(stream_key, "execution_error", {
            "execution_id": execution_id,
            "error": str(exc)
        })

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)

        raise


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="resume_workflow_execution"  # 显式任务名称
)
def resume_workflow_execution(
    self,
    execution_id: str,
    definition: Dict[str, Any],
    debug: bool = True
) -> dict:
    """
    恢复暂停的工作流执行

    从 checkpointer 恢复状态，继续执行到下一个中断点或完成。

    Args:
        execution_id: 执行 ID
        definition: 工作流定义 {nodes, edges}
        debug: 是否调试模式（默认 True）

    Returns:
        执行结果
    """
    logger.info(f"[Workflow] Resume task started", execution_id=execution_id, debug=debug)
    stream_key = f"workflow:{execution_id}"

    try:
        # Windows 兼容性：设置事件循环策略
        import sys
        if sys.platform == 'win32':
            from asyncio import WindowsSelectorEventLoopPolicy
            asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

        # 创建事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 恢复执行
            result = loop.run_until_complete(
                _resume_execution_async(execution_id, definition, debug, stream_key)
            )
            return result
        finally:
            # 清理：关闭事件循环
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    except Exception as exc:
        logger.error(f"Workflow resume failed: {execution_id}, error={exc}")

        _publish_sync(stream_key, "execution_error", {
            "execution_id": execution_id,
            "error": str(exc)
        })

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)

        raise


async def _resume_execution_async(
    execution_id: str,
    definition: Dict[str, Any],
    debug: bool,
    stream_key: str
) -> dict:
    """
    异步恢复工作流执行

    从 checkpointer 恢复状态，继续执行到下一个中断点或完成。
    """
    from datetime import datetime
    from sqlalchemy import select
    from app.db.session import async_session
    from app.models.workflow import WorkflowExecution
    from app.core.engine.graph_builder import GraphBuilder

    logger.info(f"[Resume] Resuming execution {execution_id}")

    # 1. 推送恢复事件
    _publish_sync(stream_key, "execution_resumed", {
        "execution_id": execution_id
    })

    # 2. 构建图（使用相同的配置）
    try:
        builder = GraphBuilder()
        graph = await builder.build(definition, execution_id, debug)
        logger.info(f"[Resume] Graph rebuilt successfully for execution {execution_id}")
    except Exception as e:
        logger.error(f"[Resume] Failed to rebuild graph: {e}", exc_info=True)
        raise

    # 3. 获取当前状态
    config = {"configurable": {"thread_id": execution_id}}
    current_state = await graph.aget_state(config)

    logger.info(f"[Resume] Current state: next={current_state.next}")

    # 4. 恢复执行（传入 None 表示继续，stream_mode="updates" 监听节点完成）
    try:
        async for event in graph.astream(None, config=config, stream_mode="updates"):
            # event 格式：{'node_id': output}，表示节点已执行完成
            # 处理节点完成事件
            for node_id, output in event.items():
                logger.info(f"[Resume] Node completed: {node_id}")

                _publish_sync(stream_key, "node_complete", {
                    "execution_id": execution_id,
                    "node_id": node_id,
                    "output": str(output)[:500] if output else "",
                    "status": "completed",
                })

            # 检查是否还有下一个中断点
            state = await graph.aget_state(config)
            logger.debug(f"[Resume] Current state: next={state.next}")

            if state.next:
                # 还有下一个节点，在执行前暂停
                next_node = state.next[0]
                logger.info(f"[Resume] Execution paused before next node: {next_node}")

                _publish_sync(stream_key, "execution_paused", {
                    "execution_id": execution_id,
                    "node_id": next_node,
                    "reason": "debug_breakpoint",
                    "state": state.values
                })

                # 更新数据库状态为 paused
                async with async_session() as s:
                    exec_record = (
                        await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == execution_id))
                    ).scalar_one_or_none()
                    if exec_record:
                        exec_record.status = "paused"
                        exec_record.completed_at = datetime.utcnow()
                        await s.commit()

                # 返回暂停状态
                return {
                    "execution_id": execution_id,
                    "status": "paused",
                    "next_node": next_node,
                    "state": state.values
                }

        # 执行完成
        final_state = await graph.aget_state(config)

        result = {
            "execution_id": execution_id,
            "status": "completed",
            "final_state": {
                "node_outputs": final_state.values.get("node_outputs", {}),
                "status": final_state.values.get("status", "completed"),
            }
        }

        _publish_sync(stream_key, "execution_complete", {
            "execution_id": execution_id,
            "success": True,
            "total_duration_ms": 0,
            "result": result
        })

        # 更新数据库状态为 completed
        async with async_session() as s:
            exec_record = (
                await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == execution_id))
            ).scalar_one_or_none()
            if exec_record:
                exec_record.status = "completed"
                exec_record.completed_at = datetime.utcnow()
                await s.commit()

        logger.info(f"[Resume] Execution completed: {execution_id}")
        return result

    except Exception as exc:
        logger.error(f"[Resume] Execution failed: {exc}", exc_info=True)
        _publish_sync(stream_key, "execution_error", {
            "execution_id": execution_id,
            "error": str(exc)
        })
        raise


async def _execute_workflow_async(
    execution_id: str,
    definition: Dict[str, Any],
    inputs: Dict[str, Any],
    debug: bool,
    stream_key: str
) -> dict:
    """异步执行工作流"""
    # 1. 发送开始事件
    _publish_sync(stream_key, "execution_start", {
        "execution_id": execution_id,
        "debug": debug,
        "inputs": inputs,
        "total_nodes": len(definition.get("nodes", []))
    })

    nodes = definition.get("nodes", [])
    edges = definition.get("edges", [])

    if not nodes:
        raise ValueError("Workflow definition has no nodes")

    # 2. 使用 GraphBuilder 构建 LangGraph
    from app.core.engine.graph_builder import GraphBuilder
    from app.core.engine.state import WorkflowState

    try:
        builder = GraphBuilder()
        graph = await builder.build(definition, execution_id, debug)
        logger.info(f"[Workflow] Graph built successfully for execution {execution_id}")
    except Exception as e:
        logger.error(f"[Workflow] Failed to build graph: {e}", exc_info=True)
        raise

    # 3. 准备初始状态（包含输入参数）
    initial_state = {
        "execution_id": execution_id,
        "workflow_id": "",  # 从上下文获取
        "inputs": inputs,  # 传入用户输入
        "variables": {},
        "node_outputs": {},
        "node_timings": {},
        "current_node": None,
        "status": "running",
    }

    # 4. 执行工作流
    try:
        config = {"configurable": {"thread_id": execution_id}}
        logger.info(f"[Workflow] Starting execution {execution_id} with config {config}, debug={debug}")

        # 根据是否调试模式选择不同的执行方式
        if debug:
            # 调试模式：逐步执行，支持中断
            result = await _execute_with_debug(graph, initial_state, config, stream_key, execution_id)
        else:
            # 正常模式：一次性执行完成
            result = await _execute_normal(graph, initial_state, config, stream_key, execution_id)

        return result

    except Exception as exc:
        logger.error(f"Workflow async execution failed: {exc}", exc_info=True)
        _publish_sync(stream_key, "execution_error", {
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
        logger.debug(f"[SSE] Connecting to Redis: {redis_url}")

        r = redis.from_url(redis_url)

        # 测试连接
        if not r.ping():
            logger.error("[SSE] Redis ping failed")
            return

        data = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": json.dumps(payload),
        }

        result = r.xadd(stream, data, maxlen=10000, approximate=True)
        logger.debug(f"[SSE] Published event: {event_type} to {stream}, msg_id: {result}")

    except Exception as e:
        logger.error(f"[SSE] Failed to publish event: {e}", exc_info=True)


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="execute_node_task"  # 显式任务名称
)
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
        # Windows 兼容性：设置事件循环策略
        import sys
        if sys.platform == 'win32':
            from asyncio import WindowsSelectorEventLoopPolicy
            asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                _execute_node_async(execution_id, node, stream_key)
            )
            return result
        finally:
            # 清理：关闭事件循环
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
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
    _publish_sync(stream_key, "node_start", {
        "execution_id": execution_id,
        "node_id": node["id"],
        "node_type": node["type"],
        "node_name": node.get("name", node["id"]),
    })

    result = await executor.run(state)

    _publish_sync(stream_key, "node_complete", {
        "execution_id": execution_id,
        "node_id": node["id"],
        "result": result,
        "status": "completed",
    })

    return result


async def _execute_with_debug(
    graph,
    initial_state: dict,
    config: dict,
    stream_key: str,
    execution_id: str
) -> dict:
    """
    调试模式执行：逐步执行，在中断点暂停

    使用 graph.stream() 方法，检测中断状态。
    如果在中断点，推送暂停事件并返回。
    前端调用 debugContinue 时，启动新任务恢复执行。
    """
    from datetime import datetime
    from sqlalchemy import select
    from app.db.session import async_session
    from app.models.workflow import WorkflowExecution

    logger.info(f"[Debug] Starting debug execution for {execution_id}")

    # 使用 astream 方法执行，支持中断（stream_mode="updates" 监听节点完成）
    async for event in graph.astream(initial_state, config=config, stream_mode="updates"):
        # event 格式：{'node_id': output}，表示节点已执行完成
        # 处理节点完成事件
        for node_id, output in event.items():
            logger.info(f"[Debug] Node completed: {node_id}")

            _publish_sync(stream_key, "node_complete", {
                "execution_id": execution_id,
                "node_id": node_id,
                "output": str(output)[:500] if output else "",
                "status": "completed",
            })

        # 检查是否还有下一个中断点
        state = await graph.aget_state(config)
        logger.debug(f"[Debug] Current state: next={state.next}")

        if state.next:
            # 还有下一个节点，在执行前暂停
            next_node = state.next[0]
            logger.info(f"[Debug] Execution paused before next node: {next_node}")

            _publish_sync(stream_key, "execution_paused", {
                "execution_id": execution_id,
                "node_id": next_node,
                "reason": "debug_breakpoint",
                "state": state.values
            })

            # 更新数据库状态为 paused
            async with async_session() as s:
                exec_record = (
                    await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == execution_id))
                ).scalar_one_or_none()
                if exec_record:
                    exec_record.status = "paused"
                    exec_record.completed_at = datetime.utcnow()
                    await s.commit()

            # 返回暂停状态
            return {
                "execution_id": execution_id,
                "status": "paused",
                "next_node": next_node,
                "state": state.values
            }

    # 执行完成
    final_state = await graph.aget_state(config)

    result = {
        "execution_id": execution_id,
        "status": "completed",
        "final_state": {
            "node_outputs": final_state.values.get("node_outputs", {}),
            "status": final_state.values.get("status", "completed"),
        }
    }

    _publish_sync(stream_key, "execution_complete", {
        "execution_id": execution_id,
        "success": True,
        "total_duration_ms": 0,
        "result": result
    })

    logger.info(f"[Debug] Execution completed: {execution_id}")
    return result


async def _execute_normal(
    graph,
    initial_state: dict,
    config: dict,
    stream_key: str,
    execution_id: str
) -> dict:
    """
    正常模式执行：一次性执行完成

    使用 astream_events 方法，流式输出事件。
    """
    logger.info(f"[Normal] Starting normal execution for {execution_id}")

    # 使用 astream_events 执行工作流
    async for event in graph.astream_events(initial_state, config=config, version="v2"):
        kind = event.get("event")
        name = event.get("name", "")
        data = event.get("data", {})

        logger.debug(f"[Normal] Received event: kind={kind}, name={name}")

        # 发布节点事件
        if kind == "on_chain_start":
            _publish_sync(stream_key, "node_start", {
                "execution_id": execution_id,
                "node_id": name,
                "node_name": name,
            })
        elif kind == "on_chain_end":
            _publish_sync(stream_key, "node_complete", {
                "execution_id": execution_id,
                "node_id": name,
                "output": str(data.get("output", ""))[:500],
                "status": "completed",
            })

    # 获取最终状态
    final_state = await graph.aget_state(config)

    result = {
        "execution_id": execution_id,
        "status": "completed",
        "final_state": {
            "node_outputs": final_state.values.get("node_outputs", {}),
            "status": final_state.values.get("status", "completed"),
        }
    }

    _publish_sync(stream_key, "execution_complete", {
        "execution_id": execution_id,
        "success": True,
        "total_duration_ms": 0,
        "result": result
    })

    logger.info(f"[Normal] Execution completed: {execution_id}")
    return result
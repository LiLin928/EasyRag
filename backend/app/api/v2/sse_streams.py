"""SSE 实时推送端点 (Redis Streams 版)

替代基于 PostgreSQL 的 SSE 端点，提供低延迟流式推送。
"""
import json
import asyncio
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.redis_streams import event_bus, subscribe_events
from app.sse.emitter import sse_event, sse_data
from app.sse.manager import get_sse_manager
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/sse", tags=["SSE"])


@router.get("/executions/{execution_id}/stream")
async def stream_execution_events(
    execution_id: str,
    request: Request,
    me: User = Depends(get_current_user),
):
    """
    订阅工作流执行事件流

    支持的事件类型:
    - execution_started: 执行开始
    - node_started: 节点开始
    - node_completed: 节点完成
    - node_failed: 节点失败
    - execution_completed: 执行完成
    - execution_failed: 执行失败
    """
    manager = get_sse_manager()
    connection_id = str(uuid.uuid4())
    stream_key = f"workflow:{execution_id}"
    client_ip = request.client.host if request.client else ""

    # 注册连接
    await manager.register(connection_id, stream_key, client_ip)

    try:
        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                async for stream, event in subscribe_events([stream_key]):
                    # 更新活动时间
                    await manager.update_activity(connection_id)

                    # 使用 emitter 格式化 SSE 事件
                    data = {
                        "event": event.event_type,
                        "data": event.payload,
                        "timestamp": event.timestamp,
                    }
                    yield sse_event(event.event_type, data)

                    # 执行完成/失败时结束流
                    if event.event_type in ["execution_completed", "execution_failed"]:
                        break

            except asyncio.CancelledError:
                pass
            except Exception as e:
                yield sse_event("error", {"message": str(e)})

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            }
        )
    finally:
        # 注销连接
        await manager.unregister(connection_id)


@router.get("/parse-tasks/{doc_id}/stream")
async def stream_parse_progress(doc_id: int, request: Request):
    """
    订阅文档解析进度流

    支持的事件类型:
    - task_started: 任务开始
    - task_progress: 进度更新
    - task_completed: 任务完成
    - task_failed: 任务失败
    - task_retrying: 任务重试
    """
    manager = get_sse_manager()
    connection_id = str(uuid.uuid4())
    stream_key = f"parse:{doc_id}"
    client_ip = request.client.host if request.client else ""

    # 注册连接
    await manager.register(connection_id, stream_key, client_ip)

    try:
        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                async for stream, event in subscribe_events([stream_key]):
                    # 更新活动时间
                    await manager.update_activity(connection_id)

                    data = {
                        "event": event.event_type,
                        "data": event.payload,
                        "timestamp": event.timestamp,
                    }
                    yield sse_event(event.event_type, data)

                    # 任务完成/失败时结束流
                    if event.event_type in ["task_completed", "task_failed"]:
                        break

            except asyncio.CancelledError:
                pass
            except Exception as e:
                yield sse_event("error", {"message": str(e)})

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    finally:
        # 注销连接
        await manager.unregister(connection_id)


@router.get("/agents/{chat_id}/stream")
async def stream_agent_chat(chat_id: str, request: Request):
    """
    订阅 Agent 对话流

    支持的事件类型:
    - phase: 阶段更新 (thinking/tool_calling/answering)
    - token: Token 流式输出
    - tool_start: 工具开始
    - tool_end: 工具结束
    - done: 对话完成
    - error: 错误
    """
    manager = get_sse_manager()
    connection_id = str(uuid.uuid4())
    stream_key = f"agent:{chat_id}"
    client_ip = request.client.host if request.client else ""

    # 注册连接
    await manager.register(connection_id, stream_key, client_ip)

    try:
        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                async for stream, event in subscribe_events([stream_key]):
                    # 更新活动时间
                    await manager.update_activity(connection_id)

                    data = {
                        "event": event.event_type,
                        "data": event.payload,
                        "timestamp": event.timestamp,
                    }
                    yield sse_event(event.event_type, data)

                    # 对话完成/错误时结束流
                    if event.event_type in ["done", "error"]:
                        break

            except asyncio.CancelledError:
                pass
            except Exception as e:
                yield sse_event("error", {"message": str(e)})

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    finally:
        # 注销连接
        await manager.unregister(connection_id)


@router.get("/retrieval-tests/{config_id}/stream")
async def stream_retrieval_test(config_id: int, request: Request):
    """
    订阅检索测试进度流

    支持的事件类型:
    - task_started: 测试开始
    - task_progress: 进度更新
    - task_completed: 测试完成
    - task_failed: 测试失败
    """
    manager = get_sse_manager()
    connection_id = str(uuid.uuid4())
    stream_key = f"retrieval_test:{config_id}"
    client_ip = request.client.host if request.client else ""

    # 注册连接
    await manager.register(connection_id, stream_key, client_ip)

    try:
        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                async for stream, event in subscribe_events([stream_key]):
                    # 更新活动时间
                    await manager.update_activity(connection_id)

                    data = {
                        "event": event.event_type,
                        "data": event.payload,
                        "timestamp": event.timestamp,
                    }
                    yield sse_event(event.event_type, data)

                    if event.event_type in ["task_completed", "task_failed"]:
                        break

            except asyncio.CancelledError:
                pass
            except Exception as e:
                yield sse_event("error", {"message": str(e)})

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    finally:
        # 注销连接
        await manager.unregister(connection_id)


# 批量订阅端点 (支持同时监听多个流)
@router.post("/subscribe")
async def subscribe_multiple_streams(streams: list[str], request: Request):
    """
    批量订阅多个事件流

    请求体: ["parse:123", "workflow:456", "agent:789"]
    """
    manager = get_sse_manager()
    connection_id = str(uuid.uuid4())
    stream_keys = streams
    client_ip = request.client.host if request.client else ""

    # 注册连接（使用第一个 stream 作为主键）
    primary_stream = streams[0] if streams else "multi"
    await manager.register(connection_id, primary_stream, client_ip)

    try:
        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                async for stream, event in subscribe_events(streams):
                    # 更新活动时间
                    await manager.update_activity(connection_id)

                    data = {
                        "stream": stream,
                        "event": event.event_type,
                        "data": event.payload,
                        "timestamp": event.timestamp,
                    }
                    yield sse_data(data)

            except asyncio.CancelledError:
                pass
            except Exception as e:
                yield sse_event("error", {"message": str(e)})

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    finally:
        # 注销连接
        await manager.unregister(connection_id)

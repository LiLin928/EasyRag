"""Redis Streams 事件总线

用于 SSE 实时推送，替代 PostgreSQL 事件总线。
"""
import json
import asyncio
from typing import Optional, Callable, AsyncGenerator, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import os

import redis.asyncio as aioredis


@dataclass
class Event:
    """事件数据结构"""
    event_type: str           # 事件类型: task_started/progress/completed/failed/node_start/...
    stream_key: str          # Stream key: parse:{doc_id}, workflow:{exec_id}, agent:{chat_id}
    payload: Dict[str, Any]   # 事件数据
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class RedisEventBus:
    """
    Redis Streams 事件总线
    
    替代 sse_bus_pg.py 中的 PostgreSQL 事件总线
    
    使用示例:
        # 发布事件
        event = Event(event_type="task_started", stream_key="parse:123", payload={"pct": 0})
        await event_bus.publish("parse:123", event)
        
        # 订阅事件
        async for stream, event in event_bus.subscribe(["parse:123", "workflow:456"]):
            print(f"Received: {event.event_type}")
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/2")
        self._redis: Optional[aioredis.Redis] = None
        self._maxlen = int(os.getenv("REDIS_STREAM_MAXLEN", "10000"))
        
    async def connect(self):
        """连接 Redis"""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
            )
        
    async def disconnect(self):
        """断开连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            
    async def publish(self, stream: str, event: Event) -> str:
        """
        发布事件到 Redis Stream
        
        Args:
            stream: Stream key (e.g., "parse:123", "workflow:456")
            event: 事件对象
            
        Returns:
            message_id: 消息 ID (e.g., "1693812000000-0")
        """
        await self.connect()
        
        # 序列化事件
        data = {
            "type": event.event_type,
            "timestamp": event.timestamp,
            "payload": json.dumps(event.payload),
        }
        
        # XADD 添加事件
        message_id = await self._redis.xadd(
            stream,
            data,
            maxlen=self._maxlen,
            approximate=True
        )
        return message_id
    
    async def subscribe(
        self,
        streams: list[str],
        consumer_group: str = "sse_consumers",
        consumer_name: Optional[str] = None,
        block_ms: int = 5000,
        count: int = 100
    ) -> AsyncGenerator[tuple[str, Event], None]:
        """
        订阅多个 Stream
        
        Args:
            streams: Stream key 列表
            consumer_group: 消费者组名称
            consumer_name: 消费者名称 (自动生成的 uuid)
            block_ms: 阻塞等待时间 (毫秒)
            count: 每次读取数量
            
        Yields:
            (stream_name, Event): Stream 名称和事件对象
        """
        await self.connect()
        
        if consumer_name is None:
            import uuid
            consumer_name = f"consumer-{uuid.uuid4().hex[:8]}"
        
        # 确保消费者组存在
        for stream in streams:
            try:
                await self._redis.xgroup_create(
                    stream,
                    consumer_group,
                    id="0",  # 从最早开始
                    mkstream=True
                )
            except aioredis.ResponseError as e:
                # 消费者组已存在
                if "already exists" not in str(e).lower():
                    raise
        
        # 读取消息
        while True:
            try:
                messages = await self._redis.xreadgroup(
                    groupname=consumer_group,
                    consumername=consumer_name,
                    streams={s: ">" for s in streams},  # ">" 表示只读新消息
                    count=count,
                    block=block_ms
                )
                
                for stream, entries in messages:
                    for message_id, fields in entries:
                        # 反序列化事件
                        event = Event(
                            event_type=fields["type"],
                            stream_key=stream,
                            payload=json.loads(fields["payload"]),
                            timestamp=fields.get("timestamp"),
                        )
                        yield stream, event
                        
                        # ACK 确认
                        await self._redis.xack(stream, consumer_group, message_id)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                # 记录错误但继续
                import logging
                logging.error(f"Stream read error: {e}")
                await asyncio.sleep(1)

    async def get_stream_info(self, stream: str) -> Dict[str, Any]:
        """获取 Stream 信息"""
        await self.connect()
        info = await self._redis.xinfo_stream(stream)
        return {
            "length": info.get("length", 0),
            "radix-tree-keys": info.get("radix-tree-keys", 0),
            "groups": info.get("groups", 0),
            "last-generated-id": info.get("last-generated-id"),
            "first-entry": info.get("first-entry"),
            "last-entry": info.get("last-entry"),
        }
    
    async def trim_stream(self, stream: str, maxlen: int):
        """裁剪 Stream 长度"""
        await self.connect()
        await self._redis.xtrim(stream, maxlen=maxlen, approximate=True)

    async def delete_stream(self, stream: str):
        """删除 Stream"""
        await self.connect()
        await self._redis.delete(stream)


# 全局实例
event_bus = RedisEventBus()


async def publish_event(stream: str, event_type: str, payload: Dict[str, Any]) -> str:
    """快捷发布事件函数"""
    event = Event(
        event_type=event_type,
        stream_key=stream,
        payload=payload
    )
    return await event_bus.publish(stream, event)


async def subscribe_events(
    streams: list[str],
    **kwargs
) -> AsyncGenerator[tuple[str, Event], None]:
    """快捷订阅事件函数"""
    async for stream, event in event_bus.subscribe(streams, **kwargs):
        yield stream, event

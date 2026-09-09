"""PostgreSQL SSE Event Bus."""

import asyncio
import json
from typing import AsyncGenerator
from sqlalchemy import text
from app.db.session import async_session
from app.sse.emitter import sse_event

_TERMINAL_EVENTS = {'execution_complete', 'error', 'execution_cancelled', 'execution_paused'}

async def publish(execution_id: str, event: str, data: dict) -> None:
    async with async_session() as session:
        await session.execute(
            text('INSERT INTO execution_events (execution_id, event, data) VALUES (:eid, :evt, :data)'),
            {'eid': execution_id, 'evt': event, 'data': json.dumps(data, ensure_ascii=False)}
        )
        await session.commit()

async def subscribe(execution_id: str, poll_interval: float = 0.5) -> AsyncGenerator[str, None]:
    last_seq = 0
    
    async with async_session() as session:
        # 1. SELECT 历史事件 ORDER BY seq
        result = await session.execute(
            text('SELECT event, data, seq FROM execution_events WHERE execution_id=:eid ORDER BY seq'),
            {'eid': execution_id}
        )
        for row in result.fetchall():
            last_seq = row.seq
            yield sse_event(row.event, row.data)
            if row.event in _TERMINAL_EVENTS:
                return
        
        # 2. 轮询新事件
        while True:
            await asyncio.sleep(poll_interval)
            result = await session.execute(
                text('SELECT event, data, seq FROM execution_events WHERE execution_id=:eid AND seq > :last ORDER BY seq'),
                {'eid': execution_id, 'last': last_seq}
            )
            rows = result.fetchall()
            for row in rows:
                last_seq = row.seq
                yield sse_event(row.event, row.data)
                if row.event in _TERMINAL_EVENTS:
                    return


"""PostgreSQL SSE Event Bus."""

import json
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


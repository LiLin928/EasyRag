"""PostgreSQL SSE event bus tests."""
import asyncio
import pytest
from sqlalchemy import text
from app.db.session import async_session
from app.core.engine.sse_bus_pg import publish, subscribe, _TERMINAL_EVENTS


class TestPublish:
    @pytest.mark.asyncio
    async def test_publish_inserts_event(self):
        execution_id = "test-001"
        async with async_session() as session:
            await session.execute(text("DELETE FROM execution_events"))
            await session.commit()
        await publish(execution_id, "node_start", {"node_id": "n1"})
        async with async_session() as db:
            result = await db.execute(
                text("SELECT event, data FROM execution_events WHERE execution_id=:eid"),
                {"eid": execution_id}
            )
            row = result.fetchone()
            assert row is not None
            assert row.event == "node_start"
            assert row.data == {"node_id": "n1"}

    @pytest.mark.asyncio
    async def test_publish_complex_data(self):
        execution_id = "test-002"
        async with async_session() as session:
            await session.execute(text("DELETE FROM execution_events"))
            await session.commit()
        data = {"nested": {"key": "value"}, "list": [1, 2, 3], "unicode": "中文"}
        await publish(execution_id, "node_complete", data)
        async with async_session() as db:
            result = await db.execute(
                text("SELECT data FROM execution_events WHERE execution_id=:eid"),
                {"eid": execution_id}
            )
            row = result.fetchone()
            assert row.data == data


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_yields_historical_events(self):
        execution_id = "test-sub-001"
        async with async_session() as session:
            await session.execute(text("DELETE FROM execution_events"))
            await session.execute(
                text("INSERT INTO execution_events (execution_id, event, data) VALUES (:eid, :evt, :data)"),
                {"eid": execution_id, "evt": "execution_start", "data": "{}"}
            )
            await session.execute(
                text("INSERT INTO execution_events (execution_id, event, data) VALUES (:eid, :evt, :data)"),
                {"eid": execution_id, "evt": "execution_complete", "data": "{}"}
            )
            await session.commit()
        events = []
        async for sse in subscribe(execution_id, poll_interval=0.1):
            events.append(sse)
        assert len(events) == 2
        assert "execution_start" in events[0]
        assert "execution_complete" in events[1]

    @pytest.mark.asyncio
    async def test_subscribe_sse_format(self):
        execution_id = "test-sub-002"
        async with async_session() as session:
            await session.execute(text("DELETE FROM execution_events"))
            await session.execute(
                text("INSERT INTO execution_events (execution_id, event, data) VALUES (:eid, :evt, :data)"),
                {"eid": execution_id, "evt": "test_event", "data": '{"value":42}'}
            )
            await session.execute(
                text("INSERT INTO execution_events (execution_id, event, data) VALUES (:eid, :evt, :data)"),
                {"eid": execution_id, "evt": "execution_complete", "data": "{}"}
            )
            await session.commit()
        events = []
        async for sse in subscribe(execution_id, poll_interval=0.1):
            events.append(sse)
        assert len(events) == 2
        assert events[0].startswith("event: test_event")
        assert 'data: {"value":42}' in events[0]
        assert events[0].endswith("\n\n")

    @pytest.mark.asyncio
    async def test_subscribe_polling_for_new_events(self):
        execution_id = "test-sub-003"
        async with async_session() as session:
            await session.execute(text("DELETE FROM execution_events"))
            await session.execute(
                text("INSERT INTO execution_events (execution_id, event, data) VALUES (:eid, :evt, :data)"),
                {"eid": execution_id, "evt": "execution_start", "data": "{}"}
            )
            await session.commit()
        
        received = []
        
        async def delayed_publish():
            await asyncio.sleep(0.3)
            await publish(execution_id, "node_start", {"node": 1})
            await asyncio.sleep(0.1)
            await publish(execution_id, "execution_complete", {})
        
        async def collect():
            async for sse in subscribe(execution_id, poll_interval=0.05):
                received.append(sse)
        
        await asyncio.gather(collect(), delayed_publish())
        
        assert len(received) == 3
        assert "execution_start" in received[0]
        assert "node_start" in received[1]
        assert "execution_complete" in received[2]

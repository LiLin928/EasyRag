import pytest
from sqlalchemy import text
from app.db.session import async_session


@pytest.mark.asyncio
async def test_session_can_query():
    async with async_session() as s:
        r = await s.execute(text("SELECT 1"))
        assert r.scalar() == 1

import pytest
from sqlalchemy import select
from app.db.session import async_session
from app.models.user import User


@pytest.mark.asyncio
async def test_create_and_query_user():
    async with async_session() as s:
        u = User(username="t_task5_" + str(__import__("uuid").uuid4().hex[:8]), hashed_password="x", role="admin")
        s.add(u)
        await s.commit()
        got = (await s.execute(select(User).where(User.username == u.username))).scalar_one()
        assert got.id is not None
        assert got.role == "admin"
        assert got.is_active is True

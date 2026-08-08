import pytest
from sqlalchemy import select
from app.db.session import async_session
from app.models.user import User
from app.security.init_admin import ensure_admin
from app.config import settings


@pytest.mark.asyncio
async def test_ensure_admin_idempotent():
    await ensure_admin()
    await ensure_admin()  # 重复调用不应报错或重复创建
    async with async_session() as s:
        users = (await s.execute(select(User).where(User.username == settings.init_admin_username))).scalars().all()
        assert len(users) == 1
        assert users[0].role == "admin"

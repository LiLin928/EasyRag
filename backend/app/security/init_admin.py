from sqlalchemy import select
from app.db.session import async_session
from app.models.user import User
from app.security.password import hash_password
from app.config import settings


async def ensure_admin() -> None:
    """启动时确保初始管理员存在（幂等）。"""
    async with async_session() as s:
        exists = (await s.execute(select(User).where(User.username == settings.init_admin_username))).scalar_one_or_none()
        if exists:
            return
        s.add(User(
            username=settings.init_admin_username,
            hashed_password=hash_password(settings.init_admin_password),
            display_name="Administrator",
            role="admin",
        ))
        await s.commit()

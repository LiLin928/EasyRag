"""seed（内置场景种子）单元测试。"""
import pytest
from sqlalchemy import select

from app.core.scenes import BUILTIN_SCENES
from app.core.seed import seed_builtin_scenes
from app.db.session import async_session
from app.models.scene import Scene


@pytest.mark.asyncio
async def test_seed_idempotent():
    """连续两次 seed 内置场景，每个内置 code 应恰好一条且 built_in=True（幂等）。"""
    await seed_builtin_scenes()
    await seed_builtin_scenes()
    async with async_session() as s:
        for code in BUILTIN_SCENES:
            rows = (await s.execute(select(Scene).where(Scene.code == code))).scalars().all()
            assert len(rows) == 1
            assert rows[0].built_in is True

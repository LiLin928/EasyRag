"""Scene ORM 模型单元测试。"""
import pytest
from sqlalchemy import delete, select

from app.db.session import async_session
from app.models.scene import Scene


@pytest.mark.asyncio
async def test_create_scene():
    """创建一个场景，验证 JSONB config 与 built_in 标记能正确持久化与读取。

    使用测试专用 code 并在开头清理可能残留的同名记录，保证测试可重复运行，
    且不污染内置场景（general/bidding/...）数据。
    """
    async with async_session() as s:
        await s.execute(delete(Scene).where(Scene.code == "test_scene_unit"))
        await s.commit()
        sc = Scene(code="test_scene_unit", name="通用问答-测试", config={"top_k": 5}, built_in=False)
        s.add(sc)
        await s.commit()
        got = (await s.execute(select(Scene).where(Scene.code == "test_scene_unit"))).scalar_one()
        assert got.config["top_k"] == 5
        assert got.built_in is False

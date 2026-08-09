"""模型配置服务层。

提供默认模型读取（use 优先、group 回退）、同组默认互斥、按 (grp, name) upsert，
供 langchain_factory 与 settings API 调用。
"""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.model_config import ModelConfig


async def get_default_model(grp: str, use: str | None = None, db: AsyncSession | None = None) -> ModelConfig | None:
    """读取指定分组的默认模型。

    解析顺序：优先返回 (grp, use) 且 is_default/enabled 的模型；不存在则回退到
    该 grp 下任意 is_default/enabled 的模型。两者都没有时返回 None。

    Args:
        grp: 模型分组（llm / embed / rerank）。
        use: 用途（qa / summary / rewrite / retrieval / rerank），可空。
        db: 可选外部会话；不传则自建会话。

    Returns:
        命中的默认模型，或 None。
    """
    async def _q(s: AsyncSession):
        if use:
            r = await s.execute(select(ModelConfig).where(
                ModelConfig.grp == grp, ModelConfig.use == use,
                ModelConfig.is_default == True, ModelConfig.enabled == True))
            m = r.scalar_one_or_none()
            if m:
                return m
        r = await s.execute(select(ModelConfig).where(
            ModelConfig.grp == grp, ModelConfig.is_default == True, ModelConfig.enabled == True))
        return r.scalar_one_or_none()

    if db:
        return await _q(db)
    async with async_session() as s:
        return await _q(s)


async def set_default_model(grp: str, name: str) -> None:
    """将指定 (grp, name) 设为该组唯一默认（同组互斥）。

    先清除该组所有 is_default 标记，再将目标模型置为默认。

    Args:
        grp: 模型分组。
        name: 目标模型名。
    """
    async with async_session() as s:
        await s.execute(update(ModelConfig).where(ModelConfig.grp == grp).values(is_default=False))
        await s.execute(update(ModelConfig).where(
            ModelConfig.grp == grp, ModelConfig.name == name).values(is_default=True))
        await s.commit()


async def upsert_model(m: ModelConfig) -> ModelConfig:
    """按 (grp, name) upsert 一条模型配置。

    已存在则按字段更新（仅更新非 None 字段），否则新增。

    Args:
        m: 待写入的 ModelConfig 实例。

    Returns:
        写入后的 ModelConfig 实例（已 refresh）。
    """
    async with async_session() as s:
        existing = (await s.execute(select(ModelConfig).where(
            ModelConfig.grp == m.grp, ModelConfig.name == m.name))).scalar_one_or_none()
        if existing:
            for k in ("prov", "use", "url", "api_key_enc", "params", "is_default", "enabled"):
                v = getattr(m, k)
                if v is not None:
                    setattr(existing, k, v)
            await s.commit()
            return existing
        s.add(m)
        await s.commit()
        await s.refresh(m)
        return m

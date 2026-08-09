"""启动 seed：内置场景 +（env 配置则）默认 LLM 模型。

由 main.py lifespan 调 run_seed() 完成开箱即用的初始数据。
"""
from sqlalchemy import select

from app.config import settings
from app.core.scenes import BUILTIN_SCENES
from app.db.session import async_session
from app.models.model_config import ModelConfig
from app.models.scene import Scene
from app.security.crypto import encrypt


async def seed_builtin_scenes() -> None:
    """将内置场景预设写入 DB（已存在的 code 跳过，幂等）。"""
    async with async_session() as s:
        for code, b in BUILTIN_SCENES.items():
            exists = (await s.execute(select(Scene).where(Scene.code == code))).scalar_one_or_none()
            if not exists:
                s.add(Scene(code=code, name=b["name"], description=b["description"],
                            config=b["config"], built_in=True))
        await s.commit()


async def seed_default_model_from_env() -> None:
    """若 env 配了默认 LLM，且库中尚无默认 llm，则 seed 一个（开箱即用）。"""
    if not (settings.llm_default_base_url and settings.llm_default_api_key and settings.llm_qa_model):
        return
    async with async_session() as s:
        has = (await s.execute(select(ModelConfig).where(
            ModelConfig.grp == "llm", ModelConfig.is_default == True))).scalar_one_or_none()
        if has:
            return
        m = ModelConfig(
            grp="llm", name=settings.llm_qa_model, prov="dashscope", use="qa",
            url=settings.llm_default_base_url, api_key_enc=encrypt(settings.llm_default_api_key),
            params={"temp": 0.3}, is_default=True, enabled=True,
        )
        s.add(m)
        await s.commit()


async def run_seed() -> None:
    """执行全部启动 seed：内置场景 + env 默认模型。"""
    await seed_builtin_scenes()
    await seed_default_model_from_env()

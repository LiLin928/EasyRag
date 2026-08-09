"""检索场景配置：SceneConfig + 内置场景预设 + get_scene_config。

供检索管线（Plan 4）按场景读取检索/问答参数与系统提示词。
"""
from dataclasses import dataclass

from sqlalchemy import select

from app.db.session import async_session
from app.models.scene import Scene


@dataclass
class SceneConfig:
    """场景的检索/问答参数集合（检索管线运行时读取）。"""

    code: str
    name: str
    description: str = ""
    system_prompt: str = ""
    chunk_size: int = 512
    top_k: int = 5
    vector_top_k: int = 20
    trgm_top_k: int = 20
    vector_weight: float = 0.7
    keyword_weight: float = 0.3
    rrf_k: int = 60
    rerank_enabled: bool = True
    rerank_threshold: float = 0.02
    rerank_top_n: int = 10
    navigation_enabled: bool = True
    nav_confidence_threshold: float = 0.15


_SYS_GENERAL = "你是专业文档问答助手。仅基于参考资料回答，用 [n] 标注引用，资料不足时明确告知。"
_SYS_BIDDING = "你是标书分析助手。重点关注表格/条款/资质，引用具体条款编号与页码，金额日期原文引用，对比以表格呈现。"

# 内置场景预设（启动 seed 入库，built_in=True，不可删除）
BUILTIN_SCENES = {
    "general":  {"name": "通用问答", "description": "适用于任意文档的通用检索问答",
                 "config": {"system_prompt": _SYS_GENERAL, "chunk_size": 512, "top_k": 5, "rerank_threshold": 0.02}},
    "bidding":  {"name": "标书文档", "description": "招标/投标文件，强化表格与条款",
                 "config": {"system_prompt": _SYS_BIDDING, "chunk_size": 768, "top_k": 8,
                            "rerank_threshold": 0.03, "vector_weight": 0.6, "keyword_weight": 0.4}},
    "contract": {"name": "合同文档", "description": "合同条款检索",
                 "config": {"system_prompt": _SYS_GENERAL, "chunk_size": 640, "top_k": 6}},
    "tech":     {"name": "技术文档", "description": "技术规范/手册",
                 "config": {"system_prompt": _SYS_GENERAL, "chunk_size": 600, "top_k": 6}},
    "product":  {"name": "产品文档", "description": "产品说明/手册",
                 "config": {"system_prompt": _SYS_GENERAL, "chunk_size": 512, "top_k": 5}},
}


def _from_dict(code: str, d: dict) -> SceneConfig:
    """从字典构造 SceneConfig，只取合法字段，忽略多余键。"""
    valid = {k: v for k, v in d.items() if k in SceneConfig.__dataclass_fields__}
    return SceneConfig(code=code, **valid)


async def get_scene_config(code: str | None) -> SceneConfig:
    """读取场景配置：优先 DB 中的场景，回退到内置预设，再回退到 general 默认。

    Args:
        code: 场景编码，None 时取 general。

    Returns:
        合并后的 SceneConfig。
    """
    code = code or "general"
    async with async_session() as s:
        sc = (await s.execute(select(Scene).where(Scene.code == code))).scalar_one_or_none()
        if sc:
            d = {"name": sc.name, "description": sc.description or "", **(sc.config or {})}
            return _from_dict(code, d)
    if code in BUILTIN_SCENES:
        b = BUILTIN_SCENES[code]
        return _from_dict(code, {"name": b["name"], "description": b["description"], **b["config"]})
    return _from_dict("general", {"name": "通用问答", **BUILTIN_SCENES["general"]["config"]})

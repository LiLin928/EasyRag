"""settings 相关 Pydantic 请求/响应模型（对齐前端 types/settings.ts）。

ModelDef.is_default 用 alias="def"（def 是 Python 保留字）；响应不回传 key，仅 has_key。
"""
from pydantic import BaseModel, ConfigDict, Field


class ModelDef(BaseModel):
    """模型配置请求体（前端表单字段）。"""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    prov: str
    use: str | None = None
    url: str | None = None
    key: str | None = None
    temp: float | None = None
    ctx: str | None = None
    dim: str | None = None
    is_default: bool = Field(default=False, alias="def")
    params: dict = {}


class ModelOut(BaseModel):
    """模型配置响应体（不回传 key，仅 has_key 布尔）。"""

    id: str
    grp: str
    name: str
    prov: str
    use: str | None = None
    url: str | None = None
    has_key: bool = False
    is_default: bool = False
    params: dict = {}


class SceneIn(BaseModel):
    """场景请求体。"""

    code: str
    name: str
    description: str | None = None
    config: dict


class SceneOut(BaseModel):
    """场景响应体。"""

    id: str
    code: str
    name: str
    description: str | None = None
    config: dict
    built_in: bool = False


class SceneUpdate(BaseModel):
    """场景更新请求体（部分更新，不改 code）。"""

    name: str | None = None
    description: str | None = None
    config: dict | None = None

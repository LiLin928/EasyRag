"""检索场景 ORM 模型。

scenes 表存储检索/问答场景配置（system_prompt、chunk_size、top_k、混合检索权重、
rerank 开关与阈值等），built_in 标记内置预设（不可删除）。code 唯一。
"""
from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class Scene(Base, UUIDPk, TimestampMixin):
    """检索场景表，存储每个场景的检索/问答参数与系统提示词。

    Attributes:
        code: 场景编码（唯一索引），如 general / bidding / contract。
        name: 场景显示名。
        description: 场景描述（可空）。
        config: 场景参数 JSONB（system_prompt / chunk_size / top_k / 权重 / rerank 等）。
        built_in: 是否为内置预设（内置场景不可删除）。
    """

    __tablename__ = "scenes"
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSONB)
    built_in: Mapped[bool] = mapped_column(Boolean, default=False)

"""模型配置 ORM 模型。

model_configs 表存储各 provider 的 LLM / Embedding / Rerank 模型配置，
API key 以 Fernet 加密后存于 api_key_enc。(grp, name) 唯一。
"""
from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class ModelConfig(Base, UUIDPk, TimestampMixin):
    """模型配置表，存储多 provider / 多用途模型与检索场景所需的模型定义。

    Attributes:
        grp: 模型分组，llm / embed / rerank。
        name: 模型名称（如 qwen-plus），与 grp 组合唯一。
        prov: provider 标识，dashscope / openai / ollama / azure / vllm。
        use: 用途，qa / summary / rewrite / retrieval / rerank（可空）。
        url: provider 的 API base url（可空，部分 provider 不需要）。
        api_key_enc: Fernet 加密后的 API key（可空）。
        params: 其它运行参数（temperature / dim / ctx 等），JSONB。
        is_default: 是否为当前分组的默认模型（同组建议仅一个）。
        enabled: 是否启用。
    """

    __tablename__ = "model_configs"
    __table_args__ = (UniqueConstraint("grp", "name", name="uq_model_grp_name"),)

    grp: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(128))
    prov: Mapped[str] = mapped_column(String(32))
    use: Mapped[str | None] = mapped_column(String(32), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

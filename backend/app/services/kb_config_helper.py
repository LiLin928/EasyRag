"""知识库配置获取辅助函数。"""
import uuid
from typing import Tuple, Optional

from sqlalchemy import select
from app.db.session import async_session
from app.models.knowledge_base import KnowledgeBase
from app.models.model_config import ModelConfig


async def get_kb_with_model_config(kb_id: str) -> Tuple[KnowledgeBase, Optional[ModelConfig]]:
    """获取知识库及其 Embedding 模型配置。

    Args:
        kb_id: 知识库 ID (UUID 字符串)

    Returns:
        元组: (KnowledgeBase 实例, ModelConfig 实例或 None)

    Raises:
        BizException: 知识库不存在
    """
    from app.exceptions import BizException, ErrorCode

    try:
        kb_uuid = uuid.UUID(kb_id)
    except (TypeError, ValueError) as exc:
        raise BizException(ErrorCode.PARAM_ERROR, f"无效的知识库 ID: {kb_id}") from exc

    async with async_session() as session:
        # 获取知识库
        kb = await session.get(KnowledgeBase, kb_uuid)
        if not kb:
            raise BizException(ErrorCode.NOT_FOUND, f"知识库不存在: {kb_id}")

        # 如果知识库有指定的 embedding 模型
        if kb.embedding_model_id:
            model_config = await session.get(ModelConfig, kb.embedding_model_id)
            if model_config and model_config.enabled and model_config.grp == "embed":
                return kb, model_config

        # 否则返回 None，让调用方使用默认模型
        return kb, None
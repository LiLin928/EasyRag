"""知识库服务层（CRUD）。"""
from sqlalchemy import delete, select, update

from app.db.session import async_session
from app.models.knowledge_base import KnowledgeBase
from app.services.metadata_service import ensure_default_fields


async def list_kbs(user_id):
    """列出指定用户的知识库，按创建时间倒序。"""
    async with async_session() as s:
        rows = (await s.execute(
            select(KnowledgeBase).where(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.created_at.desc()))).scalars().all()
        return rows


async def create_kb(
    user_id,
    name,
    description,
    scene,
    cover,
    *,
    retrieval_mode=None,
    child_chunk_size=None,
    child_chunk_overlap=None,
):
    """新建知识库。

    retrieval_mode/child_chunk_size/child_chunk_overlap 为父子分段配置（方案§9），
    不传时使用模型默认值。
    """
    async with async_session() as s:
        kb = KnowledgeBase(user_id=user_id, name=name, description=description, scene=scene, cover=cover)
        if retrieval_mode is not None:
            kb.retrieval_mode = retrieval_mode
        if child_chunk_size is not None:
            kb.child_chunk_size = child_chunk_size
        if child_chunk_overlap is not None:
            kb.child_chunk_overlap = child_chunk_overlap
        s.add(kb)
        await s.flush()
        await ensure_default_fields(kb.id, session=s)
        await s.commit()
        await s.refresh(kb)
        return kb


async def update_kb(kb_id, **fields):
    """更新知识库（仅更新非 None 字段）。"""
    async with async_session() as s:
        await s.execute(update(KnowledgeBase).where(KnowledgeBase.id == kb_id)
                        .values(**{k: v for k, v in fields.items() if v is not None}))
        await s.commit()
        return (await s.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))).scalar_one()


async def delete_kb(kb_id):
    """删除知识库（级联删除其文档/分块等）。"""
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.id == kb_id))
        await s.commit()

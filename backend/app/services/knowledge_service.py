"""知识库服务层（CRUD）。"""
from sqlalchemy import delete, select, update

from app.db.session import async_session
from app.models.knowledge_base import KnowledgeBase


async def list_kbs(user_id):
    """列出指定用户的知识库，按创建时间倒序。"""
    async with async_session() as s:
        rows = (await s.execute(
            select(KnowledgeBase).where(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.created_at.desc()))).scalars().all()
        return rows


async def create_kb(user_id, name, description, scene, cover):
    """新建知识库。"""
    async with async_session() as s:
        kb = KnowledgeBase(user_id=user_id, name=name, description=description, scene=scene, cover=cover)
        s.add(kb)
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

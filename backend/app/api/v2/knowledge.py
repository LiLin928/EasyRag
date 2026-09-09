"""knowledge 路由：/knowledge CRUD。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge import KBCreate, KBOut, KBUpdate
from app.services import knowledge_service as ks

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _format_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _out(kb) -> dict:
    """构造知识库响应字典。"""
    created = kb.created_at.isoformat() if kb.created_at else ""
    return KBOut(
        id=str(kb.id), name=kb.name, description=kb.description, scene=kb.scene,
        cover=kb.cover, doc_count=kb.doc_count, total_size=kb.total_size,
        chunk_count=0, last_test_at=None, created_at=created,
        desc=kb.description or "",
        docCount=kb.doc_count,
        totalSize=_format_size(kb.total_size),
        createdAt=created,
    ).model_dump()


@router.get("")
async def list_(me=Depends(get_current_user)):
    """列出当前用户的知识库。"""
    return ok([_out(k) for k in await ks.list_kbs(me.id)])


@router.get("/{kb_id}")
async def detail(kb_id: str, me=Depends(get_current_user)):
    """获取知识库详情。"""
    async with async_session() as s:
        kb = (await s.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))).scalar_one_or_none()
    return ok(_out(kb))


@router.post("")
async def create(body: KBCreate, me=Depends(get_current_user)):
    """新建知识库。"""
    kb = await ks.create_kb(me.id, body.name, body.desc, body.scene, body.cover)
    return ok(_out(kb))


@router.put("/{kb_id}")
async def update(kb_id: str, body: KBUpdate, me=Depends(get_current_user)):
    """更新知识库。"""
    kb = await ks.update_kb(kb_id, name=body.name, description=body.desc, scene=body.scene, cover=body.cover)
    return ok(_out(kb))


@router.delete("/{kb_id}")
async def delete(kb_id: str, me=Depends(get_current_user)):
    """删除知识库。"""
    await ks.delete_kb(kb_id)
    return ok({"success": True})

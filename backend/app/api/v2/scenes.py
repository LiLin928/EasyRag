"""scenes 路由：顶层场景列表（聊天页用，精简格式）。

与 /settings/scenes 不同，此处返回 {id, name, desc} 三字段，
id 为场景 code（ChatRequest.scene 传 code）。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.scene import Scene

router = APIRouter(tags=["scenes"])


@router.get("/scenes")
async def list_chat_scenes(me=Depends(get_current_user)):
    """列出聊天场景（精简格式）。"""
    async with async_session() as s:
        rows = (await s.execute(select(Scene).order_by(Scene.created_at))).scalars().all()
    return ok([{"id": sc.code, "name": sc.name, "desc": sc.description or ""} for sc in rows])

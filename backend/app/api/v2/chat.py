"""chat 路由：对话 SSE + 会话 CRUD。

POST /chat 返回 text/event-stream（SSE），前端用 fetch-event-source 消费。
会话 CRUD 对齐前端 api/chat.ts。
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.api.response import ok
from app.models.user import User
from app.schemas.chat import ChatRequest, ConversationCreate
from app.services import chat_service

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(req: ChatRequest, me: User = Depends(get_current_user)):
    """对话接口，返回 SSE 流。"""
    return StreamingResponse(
        chat_service.chat_stream(req, me.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chat/conversations")
async def list_conversations(me: User = Depends(get_current_user)):
    """列出当前用户全部会话。"""
    return ok(await chat_service.list_conversations(me.id))


@router.post("/chat/conversations")
async def create_conversation(body: ConversationCreate, me: User = Depends(get_current_user)):
    """新建会话。"""
    return ok(await chat_service.create_conversation(me.id, body.title))


@router.delete("/chat/conversations/{conv_id}")
async def delete_conversation(conv_id: str, me: User = Depends(get_current_user)):
    """删除会话（级联删除消息）。"""
    await chat_service.delete_conversation(conv_id)
    return ok(None)


@router.get("/chat/conversations/{conv_id}/messages")
async def get_history(conv_id: str, me: User = Depends(get_current_user)):
    """获取会话内全部消息。"""
    return ok(await chat_service.list_messages(conv_id))

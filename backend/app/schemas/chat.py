"""对话相关 Pydantic 请求/响应模型（对齐前端 types/chat.ts）。"""
from pydantic import BaseModel


class ChatRequest(BaseModel):
    """POST /chat 请求体。"""

    question: str
    conversation_id: str | None = None
    doc_ids: list[str] = []
    scene: str = "general"
    top_k: int | None = None


class ConversationOut(BaseModel):
    """会话响应体（对齐前端 Conversation）。"""

    id: str
    title: str
    lastTime: str
    msgCount: int


class MessageOut(BaseModel):
    """消息响应体（对齐前端 ChatMessage）。"""

    id: str
    role: str
    content: str
    references: list | None = None
    trace: dict | None = None
    usage: dict | None = None
    ts: str


class ConversationCreate(BaseModel):
    """新建会话请求体。"""

    title: str | None = None


class FeedbackCreate(BaseModel):
    """反馈请求体。"""

    messageId: str
    type: str

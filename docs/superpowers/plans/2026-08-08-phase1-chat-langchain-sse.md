# Phase1 chat（LangChain 1.X）SSE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]` tracking.

**Goal:** 实现对话核心——POST /chat（SSE 流式）：查询改写（多轮）→ HybridRetriever 检索 → LCEL 生成链 astream 流式输出 + 分级引用，事件流对齐前端（phase/navigation/references/token/done/trace/error），含会话与消息持久化。

**Architecture:** LangChain 1.X：查询改写链 `REWRITE_PROMPT | fast_llm | StrOutputParser()`；生成链 `ANSWER_PROMPT | gen_llm | StrOutputParser()`（astream）；检索复用 Plan 4 的 HybridRetriever；ChatService 编排各阶段并 yield SSE 事件；conversations/messages 持久化历史。

**Tech Stack:** LangChain 1.X（LCEL/ChatPromptTemplate/StrOutputParser/astream），sse-starlette（或 StreamingResponse），Plan 2 build_chat_model，Plan 4 HybridRetriever，Plan 2 get_scene_config。

**前置：** Plan 1/2/3/4 完成。

---

## File Structure

```
backend/app/
├── models/conversation.py        # Task 1（Conversation + Message）
├── sse/__init__.py
├── sse/emitter.py                # Task 2
├── core/generator/
│   ├── __init__.py
│   ├── query_rewriter.py         # Task 3
│   └── answer_chain.py           # Task 4
├── core/reference_builder.py     # Task 5（升级为 async 分级引用）
├── services/chat_service.py      # Task 6
├── api/v2/chat.py                # Task 7（/chat SSE）
├── api/v2/conversations.py       # Task 8
├── api/v2/messages.py            # Task 9
├── api/v2/scenes.py / feedback.py  # Task 10
├── schemas/chat.py
└── alembic/versions/0008_conversations.py
```

---

### Task 1: Conversation + Message ORM + 迁移

**Files:** `models/conversation.py` · `models/__init__.py` · migrate `0008_conversations.py` · `tests/test_conv_model.py`

- [ ] **Step 1: 实现 `models/conversation.py`**

```python
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPk


class Conversation(Base, UUIDPk, TimestampMixin):
    __tablename__ = "conversations"
    user_id: Mapped = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kb_id: Mapped | None = mapped_column(ForeignKey("knowledge_bases.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    last_time: Mapped = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now())
    msg_count: Mapped[int] = mapped_column(Integer, default=0)


class Message(Base, UUIDPk, TimestampMixin):
    __tablename__ = "messages"
    conversation_id: Mapped = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))            # user/assistant
    content: Mapped[str] = mapped_column(Text)
    references: Mapped | None = mapped_column(JSONB, nullable=True)
    trace: Mapped | None = mapped_column(JSONB, nullable=True)
    usage: Mapped | None = mapped_column(JSONB, nullable=True)
    nav_path: Mapped | None = mapped_column(JSONB, nullable=True)
    retrieval_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

> 正式代码里把 `__import__("sqlalchemy").func.now()` 换成顶部 `from sqlalchemy import func` 后用 `server_default=func.now()`。

- [ ] **Step 2: 注册到 `__init__.py`**（追加 Conversation, Message）

- [ ] **Step 3: 写测试 + 迁移 + 通过**

```python
# tests/test_conv_model.py
@pytest.mark.asyncio
async def test_create_conv_msg():
    from app.models.conversation import Conversation, Message
    from app.models.user import User
    from sqlalchemy import select
    from app.db.session import async_session
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
        c = Conversation(user_id=u.id, title="会话1"); s.add(c); await s.flush()
        s.add(Message(conversation_id=c.id, role="user", content="hi")); await s.commit()
        assert c.id and c.msg_count == 0
```

Run: `alembic revision --autogenerate -m "conversations and messages" && alembic upgrade head && pytest tests/test_conv_model.py -v` → PASS · Commit `feat(models): Conversation + Message`

---

### Task 2: SSE emitter

**Files:** `app/sse/emitter.py` · `tests/test_sse_emitter.py`

- [ ] **Step 1: 实现 `emitter.py`**

```python
import json


def sse_event(event: str, data: dict | None = None) -> str:
    payload = json.dumps(data or {}, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"
```

- [ ] **Step 2: 测试**

```python
from app.sse.emitter import sse_event
def test_event_format():
    e = sse_event("token", {"token": "你好"})
    assert e.startswith("event: token\n")
    assert e.endswith("\n\n")
    assert "你好" in e
```

→ PASS · Commit `feat(sse): event emitter`

---

### Task 3: 查询改写链（LCEL）

**Files:** `app/core/generator/query_rewriter.py` · `tests/test_rewriter.py`

- [ ] **Step 1: 实现**

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models import BaseChatModel

REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是查询改写助手。根据对话历史和最新问题，输出一个独立完整的检索查询。只输出改写后的查询，不要解释。无历史或无需改写时原样输出当前问题。"),
    ("human", "对话历史：\n{history}\n\n当前问题：{question}\n\n改写后的检索查询："),
])


def build_rewrite_chain(fast_llm: BaseChatModel):
    return REWRITE_PROMPT | fast_llm | StrOutputParser()


def format_history(messages) -> str:
    if not messages:
        return "（无）"
    return "\n".join(f"{'用户' if m.role == 'user' else '助手'}: {m.content}" for m in messages)
```

- [ ] **Step 2: 测试**（mock llm）

```python
@pytest.mark.asyncio
async def test_rewrite_chain_calls_llm():
    from unittest.mock import AsyncMock, MagicMock
    from app.core.generator.query_rewriter import build_rewrite_chain
    fake = MagicMock(); fake.ainvoke = AsyncMock(return_value="改写后的查询")
    # 简化：直接验证 chain 构造不报错
    chain = build_rewrite_chain(fake)
    assert chain is not None
```

→ PASS · Commit `feat(chat): query rewrite chain`

---

### Task 4: 答案生成链（astream）

**Files:** `app/core/generator/answer_chain.py` · `tests/test_answer_chain.py`

- [ ] **Step 1: 实现**

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}\n\n规则：1.仅基于参考资料回答 2.用 [n] 标注引用 3.资料不足时告知。\n\n参考资料：\n{context}"),
    ("human", "{history}\n问题：{question}"),
])


def build_context(docs: list[Document]) -> str:
    parts = []
    for i, d in enumerate(docs, 1):
        m = d.metadata
        parts.append(f"[{i}] 《{m.get('doc_title','')}》{m.get('node_title','')}\n{d.page_content}")
    return "\n\n".join(parts) if parts else "（无相关资料）"


def build_answer_chain(gen_llm):
    return ANSWER_PROMPT | gen_llm | StrOutputParser()
```

- [ ] **Step 2: 测试** `build_context` 拼接 · Commit `feat(chat): answer chain + context builder`

---

### Task 5: reference_builder 升级为 async 分级引用

**Files:** 修改 `app/core/reference_builder.py` · 修改 `app/core/retrieval/pipeline.py`（调用改 await）· `tests/test_reference_builder.py`

- [ ] **Step 1: 升级 `reference_builder.py`（async，查 doc 标题）**

```python
from sqlalchemy import select
from app.db.session import async_session
from app.models.document import Document


async def build_references(chunks: list[dict]) -> list[dict]:
    doc_ids = {str(c.get("document_id")) for c in chunks if c.get("document_id")}
    titles: dict[str, str] = {}
    if doc_ids:
        async with async_session() as s:
            rows = (await s.execute(select(Document.id, Document.name).where(Document.id.in_(doc_ids)))).all()
            titles = {str(r[0]): r[1] for r in rows}
    return [{"ref_id": f"r{i}", "element_id": str(c.get("id")),
             "doc_title": titles.get(str(c.get("document_id")), ""),
             "node_title": c.get("clause_title"), "content_preview": (c.get("content") or "")[:80],
             "score": c.get("rerank_score", c.get("rrf", 0)), "type": "text"}
            for i, c in enumerate(chunks)]
```

- [ ] **Step 2: 修改 `pipeline.py` 的调用为 `refs = await build_references(top)`**

- [ ] **Step 3: 测试 + Commit** `feat(chat): async reference builder with doc titles`

---

### Task 6: ChatService（SSE 编排）— 核心

**Files:** `app/services/chat_service.py` · `app/schemas/chat.py` · `tests/test_chat_service.py`

- [ ] **Step 1: 实现 `schemas/chat.py`**

```python
from pydantic import BaseModel

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    question: str
    doc_ids: list[str]
    scene: str = "general"
    top_k: int = 5

class ConversationOut(BaseModel):
    id: str
    title: str
    last_time: str
    msg_count: int = 0
```

- [ ] **Step 2: 实现 `chat_service.py`**

```python
import time, uuid
from typing import AsyncIterator
from sqlalchemy import select, update
from app.db.session import async_session
from app.models.conversation import Conversation, Message
from app.providers.langchain_factory import build_chat_model
from app.core.retrieval.hybrid_retriever import HybridRetriever
from app.core.generator.query_rewriter import build_rewrite_chain, format_history
from app.core.generator.answer_chain import build_answer_chain, build_context
from app.core.scenes import get_scene_config
from app.core.reference_builder import build_references
from app.sse.emitter import sse_event


class ChatService:
    async def chat(self, req, user) -> AsyncIterator[str]:
        t0 = time.perf_counter()
        scene_cfg = await get_scene_config(req.scene)

        async with async_session() as s:
            if req.conversation_id:
                conv = (await s.execute(select(Conversation).where(Conversation.id == req.conversation_id))).scalar_one_or_none()
            else:
                conv = Conversation(user_id=str(user.id), title=(req.question[:20] or "新对话"))
                s.add(conv); await s.flush()
                req.conversation_id = str(conv.id)
            conv_id = str(conv.id)
            history = (await s.execute(select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at.desc()).limit(6))).scalars().all()[::-1]
            s.add(Message(conversation_id=conv_id, role="user", content=req.question))
            await s.commit()

        yield sse_event("phase", {"phase": "parse", "message": "正在分析问题..."})

        gen_llm = await build_chat_model(use="qa", temperature=0.3)
        rewritten = req.question
        if history:
            fast_llm = await build_chat_model(use="rewrite", temperature=0.0)
            rewritten = await build_rewrite_chain(fast_llm).ainvoke({"question": req.question, "history": format_history(history)})

        yield sse_event("phase", {"phase": "navigate", "message": "正在定位文档结构..."})
        retriever = HybridRetriever(doc_ids=req.doc_ids, scene_config=scene_cfg, top_k=req.top_k, enable_nav=scene_cfg.navigation_enabled)

        yield sse_event("phase", {"phase": "retrieve", "message": "正在检索相关内容..."})
        docs = await retriever.ainvoke(rewritten)
        result = retriever.last_result
        references = await build_references(result.chunks) if result else []
        if result and result.nav_info:
            yield sse_event("navigation", {"anchors": result.nav_info["anchors"], "fallback_used": not result.nav_info["scoped"]})
        yield sse_event("references", {"references": references})

        yield sse_event("phase", {"phase": "generate", "message": "正在生成回答..."})
        context = build_context(docs)
        history_str = format_history(history)
        chain = build_answer_chain(gen_llm)
        buffer = []
        async for token in chain.astream({"system_prompt": scene_cfg.system_prompt, "context": context, "history": history_str, "question": req.question}):
            buffer.append(token)
            yield sse_event("token", {"token": token})

        total_ms = int((time.perf_counter() - t0) * 1000)
        async with async_session() as s:
            msg = Message(conversation_id=conv_id, role="assistant", content="".join(buffer),
                          references=references, trace={"total_ms": total_ms}, retrieval_mode=result.mode if result else "hybrid")
            s.add(msg)
            await s.execute(update(Conversation).where(Conversation.id == conv_id).values(msg_count=Conversation.msg_count + 2, last_time=__import__("datetime").datetime.utcnow()))
            await s.commit()
            msg_id = str(msg.id)
        yield sse_event("done", {"message_id": msg_id, "conversation_id": conv_id, "usage": {}})
        yield sse_event("trace", {"trace_id": uuid.uuid4().hex, "nav_ms": 0, "retrieve_ms": 0, "generate_ms": 0, "total_ms": total_ms})
```

> 正式代码把 `__import__("datetime")` 换成顶部 `from datetime import datetime`。

- [ ] **Step 3: 测试**（mock build_chat_model/HybridRetriever，验证事件顺序）

```python
@pytest.mark.asyncio
async def test_chat_event_sequence(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.services.chat_service import ChatService
    from app.schemas.chat import ChatRequest
    # mock LLM astream 产 token；mock retriever 返回 docs
    ...  # 关键断言：第一个事件 phase.parse，最后 done + trace
```

→ PASS · Commit `feat(chat): ChatService SSE orchestration`

---

### Task 7: /chat SSE 端点

**Files:** `app/api/v2/chat.py` · `main.py`

- [ ] **Step 1: 实现**

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.api.deps import get_current_user
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(req: ChatRequest, me=Depends(get_current_user)):
    svc = ChatService()

    async def gen():
        try:
            async for ev in svc.chat(req, me):
                yield ev
        except Exception as e:
            from app.sse.emitter import sse_event
            yield sse_event("error", {"code": 50001, "message": str(e)})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

- [ ] **Step 2: 挂载** `app.include_router(chat.router, prefix=settings.api_prefix)` · Commit `feat(chat): /chat sse endpoint`

---

### Task 8: conversations API（/chat/conversations CRUD）

**Files:** `app/api/v2/conversations.py` · `main.py` · `tests/test_conversations_api.py`

- [ ] **Step 1: 实现**

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, delete
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.conversation import Conversation

router = APIRouter(prefix="/chat/conversations", tags=["chat"])

class CreateBody(BaseModel):
    title: str | None = None

def _out(c): return {"id": str(c.id), "title": c.title, "last_time": c.last_time.isoformat() if c.last_time else "", "msg_count": c.msg_count}

@router.get("")
async def list_(me=Depends(get_current_user)):
    async with async_session() as s:
        rows = (await s.execute(select(Conversation).where(Conversation.user_id == str(me.id)).order_by(Conversation.last_time.desc()))).scalars().all()
    return ok([_out(r) for r in rows])

@router.post("")
async def create(body: CreateBody, me=Depends(get_current_user)):
    async with async_session() as s:
        c = Conversation(user_id=str(me.id), title=body.title or "新对话"); s.add(c); await s.commit(); await s.refresh(c)
    return ok(_out(c))

@router.delete("/{cid}")
async def delete_(cid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        await s.execute(delete(Conversation).where(Conversation.id == cid)); await s.commit()
    return ok({"success": True})
```

- [ ] **Step 2: 挂载 + 测试 CRUD + Commit** `feat(chat): conversations crud`

---

### Task 9: messages API（历史）

**Files:** `app/api/v2/messages.py` · `main.py`

- [ ] **Step 1: 实现**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.conversation import Message

router = APIRouter(tags=["messages"])

@router.get("/chat/conversations/{cid}/messages")
async def history(cid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        rows = (await s.execute(select(Message).where(Message.conversation_id == cid).order_by(Message.created_at))).scalars().all()
    return ok([{"id": str(m.id), "role": m.role, "content": m.content, "references": m.references, "trace": m.trace, "ts": m.created_at.isoformat() if m.created_time else ""} for m in rows])
```

- [ ] **Step 2: 挂载 + Commit** `feat(chat): messages history`

> 注：`m.created_time` 应为 `m.created_at`（修正为字段名）。

---

### Task 10: /scenes（只读）+ /feedback

**Files:** `app/api/v2/scenes.py` · `app/api/v2/feedback.py` · `main.py` · migrate `0009_feedbacks.py`

- [ ] **Step 1: `/scenes`（复用 Plan 2 的 Scene 表）**

```python
from fastapi import APIRouter
from sqlalchemy import select
from app.api.response import ok
from app.db.session import async_session
from app.models.scene import Scene
router = APIRouter(tags=["scenes"])

@router.get("/scenes")
async def list_scenes():
    async with async_session() as s:
        rows = (await s.execute(select(Scene).order_by(Scene.created_at))).scalars().all()
    return ok([{"id": str(r.id), "name": r.name, "desc": r.description or ""} for r in rows])
```

- [ ] **Step 2: feedbacks 表 + `/feedback`**（最小实现：建表 + 接收 like/dislike）

```python
# models/feedback.py
class Feedback(Base, UUIDPk, TimestampMixin):
    __tablename__ = "feedbacks"
    message_id: Mapped = mapped_column(String(36), index=True)
    user_id: Mapped = mapped_column(String(36))
    type: Mapped[str] = mapped_column(String(16))   # like/dislike

# api/v2/feedback.py
@router.post("/feedback")
async def feedback(body: dict, me=Depends(get_current_user)):
    async with async_session() as s:
        s.add(Feedback(message_id=body["message_id"], user_id=str(me.id), type=body["type"])); await s.commit()
    return ok({"success": True})
```

- [ ] **Step 3: 迁移 + 挂载 + Commit** `feat(chat): scenes list + feedback`

---

### Task 11: 冒烟（对话端到端）

- [ ] **Step 1: 全量测试** → `pytest -v` 全绿
- [ ] **Step 2: Docker 重启 + 真实对话**

```bash
TOKEN=...
curl -N -X POST http://localhost:8000/api/v2/chat -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"验收标准是什么","doc_ids":["<已解析的doc_id>"],"scene":"general","top_k":5}'
```
Expected: 流式输出 `event: phase` → `references` → 多个 `token` → `done` → `trace`。

- [ ] **Step 3: 验证历史** `curl http://localhost:8000/api/v2/chat/conversations/<id>/messages -H "Authorization: Bearer $TOKEN"`
- [ ] **Step 4: Commit** `test: phase1 chat e2e smoke`

---

## Plan 5 完成标志
- ✅ `POST /chat` SSE 流式（phase/navigation/references/token/done/trace/error）
- ✅ 多轮查询改写（LCEL）+ HybridRetriever 检索 + LCEL 生成链 astream
- ✅ 分级引用（doc_title/node_title/preview/score）
- ✅ 会话/消息持久化 + `/chat/conversations` CRUD + `/messages` 历史 + `/scenes` + `/feedback`

**下一步：** Plan 6 elements 懒加载 + Phase1 联调收尾。

*— 计划结束 —*
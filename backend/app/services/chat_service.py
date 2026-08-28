"""对话服务：查询改写 → 检索 → 流式生成 → SSE 事件推送。

复用 RetrievalPipeline（向量+全文+RRF+Rerank+导航）和 langchain_factory 的 LLM/Embedding。
SSE 事件对齐前端 types/chat.ts：phase / navigation / references / token / done / trace / error。
"""
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.retrieval.pipeline import RetrievalPipeline
from app.core.scenes import get_scene_config
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.conversation import Conversation, Message
from app.providers.langchain_factory import build_chat_model
from app.services.retrieval_settings_service import SYSTEM_DEFAULTS


def _system_settings() -> dict:
    """构造系统默认检索设置（格式对齐 RetrievalPipeline 期望）。"""
    return {"values": {k: {"value": v, "source": "system_default"} for k, v in SYSTEM_DEFAULTS.items()}}


def _sse(event: str, data: dict) -> str:
    """格式化 SSE 事件行。"""
    import json
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _conv_out(c: Conversation) -> dict:
    """构造会话响应字典。"""
    return {
        "id": str(c.id),
        "title": c.title or "",
        "lastTime": c.last_time or (c.created_at.isoformat() if c.created_at else ""),
        "msgCount": c.msg_count,
    }


def _msg_out(m: Message) -> dict:
    """构造消息响应字典。"""
    return {
        "id": str(m.id),
        "role": m.role,
        "content": m.content,
        "references": m.references,
        "trace": m.trace,
        "usage": m.usage,
        "ts": m.created_at.isoformat() if m.created_at else "",
    }


async def list_conversations(user_id) -> list[dict]:
    """列出用户的全部会话，按最后活跃倒序。"""
    async with async_session() as s:
        rows = (await s.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
        )).scalars().all()
        return [_conv_out(c) for c in rows]


async def create_conversation(user_id, title: str | None = None) -> dict:
    """新建会话。"""
    async with async_session() as s:
        conv = Conversation(user_id=user_id, title=title or "新对话", msg_count=0)
        s.add(conv)
        await s.commit()
        await s.refresh(conv)
        return _conv_out(conv)


async def delete_conversation(conv_id: str) -> None:
    """删除会话（级联删除消息）。"""
    async with async_session() as s:
        await s.execute(delete(Conversation).where(Conversation.id == conv_id))
        await s.commit()


async def list_messages(conv_id: str) -> list[dict]:
    """列出会话内的全部消息。"""
    async with async_session() as s:
        rows = (await s.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at)
        )).scalars().all()
        return [_msg_out(m) for m in rows]


async def chat_stream(req, user_id):
    """对话 SSE 生成器。

    yields SSE 格式字符串，前端用 fetch-event-source 消费。
    """
    t0 = time.monotonic()
    trace_id = uuid.uuid4().hex[:12]

    async with async_session() as s:
        # 确保/创建会话
        if req.conversation_id:
            conv = (await s.execute(
                select(Conversation).where(Conversation.id == req.conversation_id)
            )).scalar_one_or_none()
            if not conv:
                yield _sse("error", {"code": 40400, "message": "会话不存在"})
                return
        else:
            conv = Conversation(
                user_id=user_id,
                title=req.question[:30] if req.question else "新对话",
                msg_count=0,
            )
            s.add(conv)
            await s.flush()

        # 存 user 消息
        user_msg = Message(conversation_id=conv.id, role="user", content=req.question)
        s.add(user_msg)
        await s.flush()

        yield _sse("phase", {"phase": "parse"})

        # 查询改写（简化版：无 LLM 时直接用原问题）
        rewritten = req.question
        try:
            llm = await build_chat_model(use="rewrite")
            history = await _load_history(s, conv.id, limit=4)
            if history:
                rewrite_prompt = _build_rewrite_prompt(req.question, history)
                resp = await llm.ainvoke(rewrite_prompt)
                rewritten = resp.content.strip() if hasattr(resp, "content") else str(resp)
        except Exception:
            pass  # 改写失败时用原问题

        yield _sse("phase", {"phase": "navigate"})

        # 检索
        t_nav = time.monotonic()
        pipeline = RetrievalPipeline(settings=_system_settings())
        result = await pipeline.search(
            rewritten,
            kb_ids=None,
            doc_ids=req.doc_ids or None,
            scope=None,
            metadata_filter=None,
            top_k=req.top_k or 5,
            enable_nav=None,
            count_recall=False,
        )
        nav_ms = int((time.monotonic() - t_nav) * 1000)

        if result.nav_info:
            yield _sse("navigation", result.nav_info)

        yield _sse("phase", {"phase": "retrieve"})

        refs = result.references or []
        yield _sse("references", {"references": refs})

        yield _sse("phase", {"phase": "generate"})

        t_gen = time.monotonic()
        buffer = []

        # 流式生成
        try:
            gen_llm = await build_chat_model(use="qa")
            scene_cfg = await get_scene_config(req.scene)
            prompt = _build_prompt(req.question, refs, scene_cfg)
            async for chunk in gen_llm.astream(prompt):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    buffer.append(token)
                    yield _sse("token", {"token": token})
        except BizException as e:
            yield _sse("error", {"code": int(e.code), "message": e.message})
            return
        except Exception as e:
            # LLM 不可用时回退
            fallback = "抱歉，生成服务暂时不可用，请检查模型配置。"
            buffer.append(fallback)
            yield _sse("token", {"token": fallback})

        gen_ms = int((time.monotonic() - t_gen) * 1000)
        total_ms = int((time.monotonic() - t0) * 1000)

        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        trace = {
            "trace_id": trace_id,
            "nav_ms": nav_ms,
            "retrieve_ms": nav_ms,
            "generate_ms": gen_ms,
            "total_ms": total_ms,
        }

        # 存 assistant 消息
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content="".join(buffer),
            references=refs,
            trace=trace,
            usage=usage,
        )
        s.add(assistant_msg)
        conv.msg_count = (conv.msg_count or 0) + 2
        conv.last_time = datetime.now(timezone.utc).isoformat()
        await s.commit()
        await s.refresh(assistant_msg)

        yield _sse("done", {
            "message_id": str(assistant_msg.id),
            "conversation_id": str(conv.id),
            "usage": usage,
        })
        yield _sse("trace", trace)


async def _load_history(s: AsyncSession, conv_id, limit=4):
    """加载最近 N 条消息作为多轮历史。"""
    rows = (await s.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )).scalars().all()
    return list(reversed(rows))


def _build_rewrite_prompt(question: str, history: list) -> list:
    """构造查询改写 prompt。"""
    msgs = [{"role": "system", "content": "你是查询改写助手。根据对话历史，将用户最新问题改写为独立的检索 query。只输出改写后的 query，不加任何解释。"}]
    for m in history:
        msgs.append({"role": m.role, "content": m.content})
    msgs.append({"role": "user", "content": question})
    return msgs


def _build_prompt(question: str, refs: list, scene_cfg) -> list:
    """构造生成 prompt，注入分级引用。"""
    sys_prompt = getattr(scene_cfg, "system_prompt", "你是专业文档问答助手。仅基于参考资料回答，用 [n] 标注引用。")
    context = ""
    for i, ref in enumerate(refs):
        preview = ref.get("content_preview", "")
        context += f"[{i + 1}] {preview}\n"
    user_content = f"参考资料：\n{context}\n\n问题：{question}"
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_content},
    ]

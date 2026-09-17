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
from app.providers.trace.span_manager import traced_span
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

    注意：数据库会话在每个操作块中单独管理，避免在 yield 过程中持有连接。

    Args:
        req: 对话请求对象
        user_id: 用户 ID

    Yields:
        SSE 格式的事件字符串
    """
    import logging
    logger = logging.getLogger(__name__)

    with traced_span("chat.stream", attributes={"user_id": user_id}):
        t0 = time.monotonic()
        trace_id = uuid.uuid4().hex[:12]

        logger.info(f"[Chat] Starting chat for user {user_id}, question: {req.question[:50]}...")

        # 阶段1：初始化会话和存储用户消息
        with traced_span("chat.init_conversation"):
            conv_id = None
            async with async_session() as s:
                # 确保/创建会话
                if req.conversation_id:
                    conv = (await s.execute(
                        select(Conversation).where(Conversation.id == req.conversation_id)
                    )).scalar_one_or_none()
                    if not conv:
                        yield _sse("error", {"code": 40400, "message": "会话不存在"})
                        return
                    conv_id = conv.id
                else:
                    conv = Conversation(
                        user_id=user_id,
                        title=req.question[:30] if req.question else "新对话",
                        msg_count=0,
                    )
                    s.add(conv)
                    await s.flush()
                    conv_id = conv.id

                # 存 user 消息
                user_msg = Message(conversation_id=conv_id, role="user", content=req.question)
                s.add(user_msg)
                await s.commit()
                logger.info(f"[Chat] Conversation {conv_id} initialized")

        yield _sse("phase", {"phase": "parse"})

        # 阶段2：查询改写（独立会话）
        with traced_span("chat.rewrite"):
            rewritten = req.question
            try:
                logger.info("[Chat] Trying to build LLM model for rewrite")
                llm = await build_chat_model(use="rewrite")
                logger.info("[Chat] Rewrite LLM built successfully")

                async with async_session() as s:
                    history = await _load_history(s, conv_id, limit=4)
                    logger.info(f"[Chat] Loaded {len(history)} history messages")

                    if history:
                        rewrite_prompt = _build_rewrite_prompt(req.question, history)
                        logger.info("[Chat] Calling LLM for rewrite...")
                        # 注入 tracing callbacks
                        from app.providers.trace.factory import get_tracing_callbacks
                        callbacks = get_tracing_callbacks()
                        config = {"callbacks": callbacks} if callbacks else {}
                        resp = await llm.ainvoke(rewrite_prompt, config=config)
                        rewritten = resp.content.strip() if hasattr(resp, "content") else str(resp)
                        logger.info(f"[Chat] Query rewritten: {rewritten[:50]}...")
                    else:
                        logger.info("[Chat] No history, skip rewrite")
            except BizException as e:
                logger.warning(f"[Chat] Rewrite failed (BizException): {e.message}, using original question")
            except Exception as e:
                logger.warning(f"[Chat] Rewrite failed: {e}, using original question")

        yield _sse("phase", {"phase": "navigate"})

        # 阶段3：检索（仅当指定知识库/文档时）
        with traced_span("chat.retrieval"):
            t_nav = time.monotonic()
            refs = []
            nav_ms = 0

            # 判断是否需要检索：有知识库或文档时才检索
            need_retrieval = req.doc_ids or req.kb_ids

            if need_retrieval:
                try:
                    pipeline = RetrievalPipeline(settings=_system_settings())
                    result = await pipeline.search(
                        rewritten,
                        kb_ids=req.kb_ids,
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
                except BizException as e:
                    logger.error(f"[Chat] Retrieval failed (BizException): {e.message}")
                    yield _sse("error", {"code": int(e.code), "message": e.message})
                    return
                except Exception as e:
                    logger.error(f"[Chat] Retrieval failed: {e}", exc_info=True)
                    yield _sse("error", {"code": 50001, "message": f"检索失败: {str(e)}"})
                    return
            else:
                # 简单对话：跳过检索
                logger.info("[Chat] No KB/docs specified, skipping retrieval (simple chat)")
                yield _sse("phase", {"phase": "skip_retrieve"})
                yield _sse("references", {"references": []})

        yield _sse("phase", {"phase": "generate"})

        t_gen = time.monotonic()
        buffer = []

        # 阶段4：流式生成
        with traced_span("chat.generate"):
            # 先加载历史消息
            history = []
            async with async_session() as s:
                history = await _load_history(s, conv_id, limit=6)  # 最近6条消息
                logger.info(f"[Chat] Loaded {len(history)} history messages for generation")

            try:
                logger.info(f"[Chat] Building LLM model for use=qa")
                gen_llm = await build_chat_model(use="qa")
                logger.info(f"[Chat] LLM model built successfully, provider: {type(gen_llm).__name__}")
                scene_cfg = await get_scene_config(req.scene)
                prompt = _build_prompt(req.question, refs, scene_cfg, history)  # 传递历史消息
                logger.info(f"[Chat] Starting LLM stream for question: {req.question[:50]}...")
                # 注入 tracing callbacks
                from app.providers.trace.factory import get_tracing_callbacks
                callbacks = get_tracing_callbacks()
                config = {"callbacks": callbacks} if callbacks else {}
                token_count = 0
                async for chunk in gen_llm.astream(prompt, config=config):
                    token = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if token:
                        buffer.append(token)
                        token_count += 1
                        logger.debug(f"[Chat] Token #{token_count}: {token[:20]}...")
                        yield _sse("token", {"token": token})
                logger.info(f"[Chat] LLM stream completed, generated {len(buffer)} tokens, sent {token_count} SSE events")
            except BizException as e:
                logger.error(f"[Chat] BizException: {e.message}")
                yield _sse("error", {"code": int(e.code), "message": e.message})
                return
            except Exception as e:
                # LLM 不可用时回退
                logger.error(f"[Chat] Exception during LLM call: {e}", exc_info=True)
                fallback = "抱歉，生成服务暂时不可用，请检查模型配置。"
                buffer.append(fallback)
                yield _sse("token", {"token": fallback})

        gen_ms = int((time.monotonic() - t_gen) * 1000)
        total_ms = int((time.monotonic() - t0) * 1000)

        # 估算token数量（中文字符约1.5 tokens，英文单词约1 token）
        # 简单估算：总字符数 / 2
        estimated_tokens = len("".join(buffer)) // 2
        usage = {
            "prompt_tokens": 0,
            "completion_tokens": estimated_tokens,
            "total_tokens": estimated_tokens
        }
        trace = {
            "trace_id": trace_id,
            "nav_ms": nav_ms,
            "retrieve_ms": nav_ms,
            "generate_ms": gen_ms,
            "total_ms": total_ms,
        }

        # 阶段5：保存结果（独立会话）
        with traced_span("chat.save_result"):
            try:
                async with async_session() as s:
                    # 重新加载会话
                    conv = (await s.execute(
                        select(Conversation).where(Conversation.id == conv_id)
                    )).scalar_one_or_none()

                    if conv:
                        # 存 assistant 消息
                        assistant_msg = Message(
                            conversation_id=conv_id,
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
                            "conversation_id": str(conv_id),
                            "usage": usage,
                        })
                        yield _sse("trace", trace)
                        logger.info(f"[Chat] Chat completed, conversation {conv_id} updated")
                    else:
                        logger.error(f"[Chat] Conversation {conv_id} not found when saving result")
                        yield _sse("error", {"code": 50001, "message": "会话丢失，请重试"})
            except Exception as e:
                logger.error(f"[Chat] Failed to save result: {e}", exc_info=True)
                yield _sse("error", {"code": 50001, "message": f"保存结果失败: {str(e)}"})


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


def _build_prompt(question: str, refs: list, scene_cfg, history: list = None) -> list:
    """构造生成 prompt，注入分级引用和历史消息。

    Args:
        question: 用户当前问题
        refs: 检索到的参考资料列表
        scene_cfg: 场景配置
        history: 对话历史消息列表

    Returns:
        构造好的消息列表，格式为 [{"role": "system/user/assistant", "content": "..."}]
    """
    sys_prompt = getattr(scene_cfg, "system_prompt", "你是专业文档问答助手。仅基于参考资料回答，用 [n] 标注引用。")

    # 如果没有参考资料，使用简单对话 prompt
    if not refs:
        sys_prompt = "你是友好的对话助手，请用自然、专业的方式回答用户的问题。"

    # 构建消息列表
    msgs = [{"role": "system", "content": sys_prompt}]

    # 添加历史消息（如果有）
    if history:
        for m in history:
            msgs.append({"role": m.role, "content": m.content})

    # 添加当前用户消息
    if refs:
        # 有参考资料时，注入引用
        context = ""
        for i, ref in enumerate(refs):
            preview = ref.get("content_preview", "")
            context += f"[{i + 1}] {preview}\n"
        user_content = f"参考资料：\n{context}\n\n问题：{question}"
        msgs.append({"role": "user", "content": user_content})
    else:
        # 简单对话
        msgs.append({"role": "user", "content": question})

    return msgs

# EasyRAG 后端设计方案 — Phase 2/3 详细设计（LangChain 1.X）

> **版本**：V1.0
> **日期**：2026-08-08
> **状态**：详细设计（Phase2/3 模块展开，chat/agents 采用 LangChain 1.X）
> **关联文档**：
> - `docs/backend-plans/后端开发设计方案.md`（主方案，本文档修订其 §5.7 chat 与 §5.12 agents）
> - `新版RAG需求设计文档_V2.md` / `新版RAG需求设计文档_V2_workflow.md`
> - 前端契约：`frontend/src/api/*.ts`、`frontend/src/types/*.ts`

---

## 0. 文档说明

### 0.1 本文档定位

主方案（`后端开发设计方案.md`）已对齐 16 项架构决策，但 Phase2/3 的 workflow/agents/tools/skills/mcp/todos 六个模块仅给出**蓝图表与一句话设计**。本文档将它们展开为**可落地的详细设计**，并据用户要求将 **chat 与 agents 改为基于 LangChain 1.X 实现**。

本文档是后续各模块 TDD 实施计划（writing-plans 产出）的 **spec 基础**：架构、数据流、接口契约、核心代码骨架均已确定，落地时按模块拆分逐步骤 TDD plan。

### 0.2 对主方案的修订点

| 主方案章节 | 原设计 | 本文修订 |
|-----------|--------|---------|
| §5.2 provider 抽象层 | 自研 LLM/Embedding/Rerank provider | 保留自研 provider 配置层，**上层改用 LangChain 1.X 的 `init_chat_model`/`init_embeddings` 包装**，复用 model_configs |
| §5.7 对话服务 | 裸 OpenAI SDK + 自研查询改写/检索/生成 | **改为 LangChain 1.X**：LCEL chain + 自定义 HybridRetriever(BaseRetriever) + astream 流式 |
| §5.12 agents | OpenAI 函数调用 + 自研 ReAct loop | **改为 LangChain 1.X**：`langgraph.prebuilt.create_react_agent` + `@tool` |
| §5.12 / §8.4 tracing | structlog + 可选 Langfuse | **可切换 TracingProvider**：`langsmith` / `langfuse`(自部署) / `none`，环境变量切换，零业务代码侵入 |
| §5.11 工作流 | LangGraph（已定） | 细化为 12 种节点执行器 + 变量系统 + checkpoint 完整设计 |

### 0.3 LangChain 1.X 引入的影响

- **统一抽象**：chat 的查询改写/生成、agents 的推理、workflow 的 LLM 节点、RAG 节点全部复用同一套 LangChain ChatModel/Prompt/工具抽象，DRY。
- **流式标准化**：`astream` / `astream_events(version="v2")` 统一 token/事件流，SSE 出口只需适配。
- **工具生态**：agents 与 workflow 的 tool 节点共享 `@tool` 工具池；MCP 通过 `langchain-mcp-adapters` 接入。
- **可观测**：LangSmith 一处配置，chat/agent/workflow 的 LLM 调用自动 trace。

---

## 1. LangChain 1.X 集成总览

### 1.1 包结构与版本

```toml
# backend/pyproject.toml（在主方案附录 C 基础上新增/调整）
dependencies = [
  # —— LangChain 1.X 核心 ——
  "langchain>=1.0",              # 主包（含 init_chat_model/init_embeddings、LCEL、prompts）
  "langchain-core>=1.0",         # 抽象基类（BaseRetriever/BaseTool/Runnable/Document）
  "langchain-postgres>=0.0.10",  # PGVectorStore（可选，我们主要用自建 retriever）
  "langchain-community>=1.0",    # ChatTongyi 等社区集成（可选）
  # —— LangGraph（工作流 + agents 推理）——
  "langgraph>=0.2",              # StateGraph + create_react_agent
  "langgraph-checkpoint-postgres>=2.0",  # PostgresSaver
  # —— MCP 适配（Phase2）——
  "langchain-mcp-adapters>=0.1", # MCP server → LangChain tools
  # —— Tracing ——
  "langsmith>=0.1",              # LangChain 原生 tracing
  # 保留：fastapi/sqlalchemy/pgvector/arq/openai 等（见主方案附录 C）
]
```

> **版本锁定**：LangChain 1.X 是 2025 年大版本重组后的稳定线（`langchain-core` 为稳定 ABI）。本方案代码以 **1.X API** 为准；具体次版本号落地时按 `pyproject.toml` 锁定。

### 1.2 与现有 provider 抽象层的关系

```
model_configs 表（settings 模块配置：grp/name/prov/use/url/key/params/is_default）
        │
        ▼
SettingsService.get_default_model(grp, use)   ← 仍是配置来源（单一真相）
        │
        ▼
┌─────────────────────────────────────────────────┐
│  LangChainModelFactory（新增，桥接层）            │
│    build_chat_model(use)  → BaseChatModel        │  ← init_chat_model()
│    build_embeddings()     → Embeddings           │  ← init_embeddings()
│    build_reranker()       → 自研 RerankProvider  │  （LangChain 无标准 rerank 抽象，保留自研）
└─────────────────────────────────────────────────┘
        │
        ▼
   被 chat / agents / workflow(LM/rag 节点) / skills 复用
```

**桥接层代码**（`app/providers/langchain_factory.py`）：

```python
from functools import lru_cache
from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from app.services.settings_service import get_default_model
from app.security.crypto import decrypt

# ---------- ChatModel ----------
def build_chat_model(use: str = "qa", **overrides) -> BaseChatModel:
    """按用途(qa/summary/rewrite)取默认 llm 配置，构造 LangChain ChatModel"""
    cfg = get_default_model("llm", use)          # model_configs 记录
    params = {**(cfg.params or {}), **overrides}
    common = {
        "model": cfg.name,
        "temperature": params.get("temp", 0.7),
        "max_tokens": int(params.get("max_tokens", 2048)) if params.get("max_tokens") else None,
    }
    if cfg.prov in ("openai", "dashscope", "vllm", "siliconflow"):
        # OpenAI 兼容：DashScope/vLLM/SiliconFlow 都走 openai provider + base_url
        return init_chat_model(
            model_provider="openai",
            base_url=cfg.url,
            api_key=decrypt(cfg.api_key_enc),
            **common,
        )
    if cfg.prov == "ollama":
        return init_chat_model(model_provider="ollama", base_url=cfg.url, **common)
    if cfg.prov == "azure":
        return init_chat_model(
            model_provider="azure_openai",
            azure_endpoint=cfg.url,
            api_key=decrypt(cfg.api_key_enc),
            **common,
        )
    raise ValueError(f"Unsupported llm provider: {cfg.prov}")

# ---------- Embeddings ----------
def build_embeddings() -> Embeddings:
    cfg = get_default_model("embed", "retrieval")
    dim = (cfg.params or {}).get("dim")
    if cfg.prov in ("openai", "dashscope", "vllm", "siliconflow"):
        kw = dict(model_provider="openai", model=cfg.name, base_url=cfg.url, api_key=decrypt(cfg.api_key_enc))
        if dim: kw["dimensions"] = int(dim)
        return init_embeddings(**kw)
    if cfg.prov == "ollama":
        return init_embeddings(model_provider="ollama", model=cfg.name, base_url=cfg.url)
    raise ValueError(f"Unsupported embedding provider: {cfg.prov}")
```

> **关键**：`build_chat_model(use)` 让 settings 页面切换默认模型时**无需改任何业务代码**——chat 生成用 `qa`、查询改写用 `rewrite`、摘要用 `summary`、agent 推理用 `qa`，各自取默认配置。

### 1.3 Tracing：可切换 TracingProvider（LangSmith ↔ 自部署 Langfuse）

> 决策（2026-08-08 修订）：tracing 做成**可切换**，避免数据出境锁定。三种模式经 `TRACING_PROVIDER` 配置切换，chat/agent/workflow 的 LLM 调用**零业务代码侵入**。

**配置**（`app/config.py` + `.env`）：
```python
TRACING_PROVIDER: str = "none"        # langsmith | langfuse | none
# LangSmith（云 或 自部署开源版）
LANGSMITH_API_KEY: str | None = None
LANGSMITH_PROJECT: str = "easyrag"
LANGSMITH_ENDPOINT: str | None = None # 自部署开源版时填
# Langfuse（自部署）
LANGFUSE_PUBLIC_KEY: str | None = None
LANGFUSE_SECRET_KEY: str | None = None
LANGFUSE_HOST: str = "http://langfuse:3000"   # 自部署地址
```

**实现**（`app/providers/trace/factory.py`，启动时一次性配置）：
```python
import os
def configure_tracing():
    p = settings.TRACING_PROVIDER
    if p == "langsmith":
        # LangChain 1.x 经环境变量自动启用，零代码侵入
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ.setdefault("LANGSMITH_API_KEY", settings.LANGSMITH_API_KEY)
        os.environ.setdefault("LANGSMITH_PROJECT", settings.LANGSMITH_PROJECT)
        if settings.LANGSMITH_ENDPOINT:
            os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    elif p == "langfuse":
        # 自部署 Langfuse：装 langfuse，注册 LangChain 全局 callback
        from langfuse.callback import CallbackHandler
        from langchain_core.globals import set_callbacks
        set_callbacks([CallbackHandler(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )])
    # none：不做任何配置（开发期省流量）
```

**启动注入**：`main.py` 启动时调 `configure_tracing()` 一次，之后所有 `llm.invoke` / `chain.astream` / agent / workflow 的 LLM 节点自动上报 trace。

| 模式 | 数据去向 | 适用 |
|------|---------|------|
| `langsmith` | LangSmith 云（或自部署开源版 via `LANGSMITH_ENDPOINT`） | 用 LangChain 全家桶、要原生体验 |
| `langfuse` | 自部署 Langfuse（`LANGFUSE_HOST`） | 数据不出域、企业内网 |
| `none` | 关闭 | 开发期 |

> Langfuse 自部署：`docker-compose.yml` 增加 `langfuse` + 其依赖 postgres 服务（Phase3 运维，见 §10）。切换时改 `TRACING_PROVIDER` + 对应密钥即可，**不改业务代码**。LangSmith 与 Langfuse 也可共存（同时启用两套 callback），但一般按需选一。

### 1.4 LCEL 组合范式（本方案的统一风格）

| 场景 | LCEL 写法 |
|------|----------|
| 查询改写 | `rewrite_prompt \| fast_llm \| StrOutputParser()` |
| 答案生成 | `answer_prompt \| gen_llm \| StrOutputParser()` |
| 带检索的 RAG | `{"context": retriever, "question": RunnablePassthrough()} \| answer_prompt \| llm` |
| 结构化输出 | `prompt \| llm \| JsonOutputParser()` |

---

## 2. chat 模块重构（LangChain 1.X）— Phase1

> 修订主方案 §5.7。Phase1 核心，需立即落地。本节给出完整代码骨架。

### 2.1 重构前后对比

| 维度 | 主方案（裸 SDK） | 本设计（LangChain 1.X） |
|------|----------------|----------------------|
| 查询改写 | 手写 prompt + openai 调用 | `rewrite_prompt \| fast_llm \| StrOutputParser()` |
| 检索 | 自研 pipeline 函数 | 包装为 `HybridRetriever(BaseRetriever)`，可被任何 chain 复用 |
| 生成 | 手写流式循环 | `answer_chain.astream()` |
| 工具/agent 复用 | 无 | chat 也能挂工具演进为 agent |
| tracing | 手动 | LangSmith 自动 |

### 2.2 文件结构

```
app/
├── providers/langchain_factory.py        # §1.2 桥接层
├── core/retrieval/
│   ├── hybrid_retriever.py               # BaseRetriever 实现（新）
│   └── pipeline.py                       # 原 vector/fulltext/rrf/rerank（被 retriever 调用）
├── core/generator/
│   ├── query_rewriter.py                 # LCEL 改写链
│   ├── prompt_builder.py                 # ChatPromptTemplate + 分级引用
│   └── answer_chain.py                   # 生成链
└── services/chat_service.py              # 编排 → SSE
```

### 2.3 HybridRetriever（BaseRetriever 实现）

> 把主方案的混合检索管线（pgvector + pg_trgm + RRF + 条件 Rerank）包装成 LangChain 标准 retriever，这样既能被 `chat` 用，也能被 Phase2 的 `workflow rag 节点` / `agent` 直接复用。

```python
# app/core/retrieval/hybrid_retriever.py
from typing import List
from langchain_core.callbacks import CallbackManagerForRetrieverRun, AsyncCallbackManagerForRetrieverRun
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from pydantic import PrivateAttr
from app.core.retrieval.pipeline import RetrievalPipeline, RetrievalResult
from app.core.scenes import SceneConfig


class HybridRetriever(BaseRetriever):
    """混合检索器：向量(pgvector)+全文(pg_trgm)+RRF+条件Rerank，可选结构导航。

    实现为 LangChain BaseRetriever，使其可被 LCEL chain、agent、workflow rag 节点复用。
    """
    kb_ids: List[str]
    doc_ids: List[str]
    scene_config: SceneConfig
    top_k: int = 5
    enable_nav: bool = True

    _pipeline: RetrievalPipeline = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        self._pipeline = RetrievalPipeline(scene_config=self.scene_config)

    @property
    def last_result(self) -> RetrievalResult | None:
        """最近一次检索的完整结果（含 references/nav_info/mode），供 chat 组装引用"""
        return self._pipeline.last_result

    # 仅实现 async 版（LangChain 1.x 允许只实现 _aget_relevant_documents）；
    # 同步场景由调用方 await/ainvoke 驱动，避免在 async 上下文里 run_until_complete 的隐患。
    async def _aget_relevant_documents(self, query: str, *, run_manager: AsyncCallbackManagerForRetrieverRun) -> List[Document]:
        result = await self._pipeline.search(
            query=query, doc_ids=self.doc_ids, top_k=self.top_k, enable_nav=self.enable_nav,
        )
        return [
            Document(
                page_content=c.content,
                metadata={
                    "chunk_id": str(c.id), "doc_id": str(c.document_id),
                    "doc_title": c.doc_title, "node_title": c.clause_title,
                    "page_number": c.page_number, "section_path": c.section_path,
                    "score": c.score, "element_count": c.element_count,
                },
            )
            for c in result.chunks
        ]
```

### 2.4 查询改写链（LCEL）

```python
# app/core/generator/query_rewriter.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage

REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "你是一个查询改写助手。根据对话历史和用户最新问题，输出一个**独立完整**的检索用查询。"
     "只输出改写后的查询，不要解释。若无历史或无需改写，原样输出当前问题。"),
    ("history", "{history}"),
    ("human", "当前问题：{question}\n\n改写后的检索查询："),
])

def build_rewrite_chain(fast_llm: BaseChatModel):
    return REWRITE_PROMPT | fast_llm | StrOutputParser()

def format_history(messages: list) -> str:
    """把最近 N 轮 user/assistant 消息格式化为文本（无历史返回空串，chain 会原样输出问题）"""
    if not messages:
        return ""
    return "\n".join(f"{'用户' if m.role == 'user' else '助手'}: {m.content}" for m in messages)
```

### 2.5 答案生成链（分级引用 prompt）

```python
# app/core/generator/prompt_builder.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "{system_prompt}\n\n"
     "规则：\n1. 仅基于下方参考资料回答，不要编造\n"
     "2. 使用 [n] 标注引用来源，n 为资料编号\n"
     "3. 资料不足时明确告知\n\n"
     "参考资料：\n{context}"),
    ("history", "{history}"),
    ("human", "{question}"),
])

def build_context(docs: list[Document]) -> str:
    """分级引用 Level1：资料编号 + 文档名 + 章节 + 内容预览"""
    parts = []
    for i, d in enumerate(docs, 1):
        meta = d.metadata
        parts.append(
            f"[{i}] 《{meta.get('doc_title','')}》{meta.get('node_title','')}\n{d.page_content}"
        )
    return "\n\n".join(parts) if parts else "（无相关资料）"

def build_answer_chain(gen_llm):
    return ANSWER_PROMPT | gen_llm | StrOutputParser()
```

### 2.6 chat_service 完整编排（SSE 流式）

```python
# app/services/chat_service.py
import time, uuid
from typing import AsyncIterator
from app.providers.langchain_factory import build_chat_model, build_embeddings
from app.core.retrieval.hybrid_retriever import HybridRetriever
from app.core.generator.query_rewriter import build_rewrite_chain, format_history
from app.core.generator.prompt_builder import ANSWER_PROMPT, build_context
from app.core.generator.answer_chain import build_answer_chain
from app.core.scenes import get_scene_config
from app.core.reference_builder import build_references
from app.sse.emitter import SSE
from app.models import Message

class ChatService:
    async def chat(self, req, user) -> AsyncIterator:
        t0 = time.perf_counter()
        conv = await self._ensure_conversation(req.conversation_id, req.doc_ids, req.scene, user.id)
        history = await self._load_history(conv.id, limit=6)
        await self._save_message(conv.id, "user", req.question)

        scene_cfg = get_scene_config(req.scene)
        gen_llm = build_chat_model(use="qa", temperature=0.3)
        fast_llm = build_chat_model(use="rewrite", temperature=0.0)

        # --- 阶段 1: 解析 + 查询改写 ---
        yield SSE.phase("parse", "正在分析问题...")
        if history:
            rewritten = await build_rewrite_chain(fast_llm).ainvoke({
                "question": req.question, "history": format_history(history),
            })
        else:
            rewritten = req.question

        # --- 阶段 2: 导航 ---
        yield SSE.phase("navigate", "正在定位文档结构...")
        retriever = HybridRetriever(
            kb_ids=req.kb_ids, doc_ids=req.doc_ids, scene_config=scene_cfg,
            top_k=req.top_k or 5, enable_nav=scene_cfg.navigation_enabled,
        )

        # --- 阶段 3: 检索 ---
        yield SSE.phase("retrieve", "正在检索相关内容...")
        docs = await retriever.ainvoke(rewritten)
        references = build_references(retriever.last_result.chunks)
        if retriever.last_result and retriever.last_result.nav_info:
            yield SSE.navigation(retriever.last_result.nav_info.anchors)
        yield SSE.references(references)

        # --- 阶段 4: 流式生成 ---
        yield SSE.phase("generate", "正在生成回答...")
        context = build_context(docs)
        buffer = []
        chain = build_answer_chain(gen_llm)
        async for token in chain.astream({
            "system_prompt": scene_cfg.system_prompt, "context": context,
            "history": format_history(history), "question": req.question,
        }):
            buffer.append(token)
            yield SSE.token(token)

        # --- 阶段 5: 持久化 + done/trace ---
        t1 = time.perf_counter()
        assistant = await self._save_message(
            conv.id, "assistant", "".join(buffer),
            references=references,
            trace={"total_ms": int((t1 - t0) * 1000)},
            retrieval_mode=retriever.last_result.mode if retriever.last_result else "hybrid",
        )
        yield SSE.done(message_id=str(assistant.id), conversation_id=str(conv.id), usage={})
        yield SSE.trace(trace_id=str(uuid.uuid4()),
                        nav_ms=0, retrieve_ms=0, generate_ms=0,
                        total_ms=int((t1 - t0) * 1000))
```

> **SSE 事件名严格对齐前端** `types/chat.ts`：`phase`/`navigation`/`references`/`token`/`done`/`trace`/`error`。

### 2.7 落地 TDD 要点（writing-plans 展开）

chat 重构落地时的关键测试（TDD），后续 writing-plans 会拆为逐步骤：
1. `test_langchain_factory_build_chat_model`：mock model_configs，验证按 provider 构造正确的 ChatModel。
2. `test_hybrid_retriever_returns_documents`：mock RetrievalPipeline，验证 retriever 返回 `Document[]` 且 metadata 含 chunk_id/score。
3. `test_rewrite_chain_with_history`：验证有历史时调用 fast_llm 改写，无历史时原样返回。
4. `test_answer_chain_streams_tokens`：mock gen_llm.astream，验证 token 逐个 yield。
5. `test_chat_service_sse_event_sequence`：端到端，断言 SSE 事件顺序 = parse→navigate→retrieve→references→generate→token+→done→trace。

---

## 3. agents 模块（LangChain 1.X）— Phase2

> 修订主方案 §5.12。用 `langgraph.prebuilt.create_react_agent` + `@tool`，工具来自 tools/skills/mcp/workflow/rag 五类。

### 3.1 定位与端点

agent = **可自主调用工具的 LLM 推理器**。与 chat（固定 RAG 管线）并列：

| 入口 | 模式 | 适用 |
|------|------|------|
| `POST /chat`（Phase1） | 固定检索→生成管线 | 文档问答，强引用 |
| `POST /agents/:id/chat`（Phase2 新增，SSE） | agent 自主推理，按需调工具 | 复杂任务（调 API、跑工作流、检索、问 MCP） |

> 前端 `api/agent.ts` 当前仅 CRUD；agent 对话端点 Phase2 后端先行，前端补 UI（或复用 chat 页面加 agent 选择器）。

CRUD（对齐前端 `types/agent.ts`）已在主方案 §4.3 建表，本节聚焦**执行**。

### 3.2 文件结构

```
app/
├── services/agent_service.py          # 编排：加载配置→聚工具→create_react_agent→流式
├── core/agent/
│   ├── tool_registry.py               # 五类资源 → LangChain BaseTool 聚合
│   ├── tool_adapters/
│   │   ├── http_tool.py               # Tool(HTTP) → BaseTool
│   │   ├── python_tool.py             # Tool(Python) → BaseTool（走代码沙箱）
│   │   ├── builtin_tools.py           # 内置工具
│   │   ├── rag_tool.py                # 文档检索工具（复用 HybridRetriever）
│   │   ├── workflow_tool.py           # 工作流作为工具
│   │   └── mcp_tools.py               # MCP server 工具（langchain-mcp-adapters）
│   └── memory.py                      # 会话记忆（LangGraph thread / DB 历史）
└── api/v2/agents.py                   # CRUD + POST /:id/chat (SSE)
```

### 3.3 工具聚合（核心）

```python
# app/core/agent/tool_registry.py
from langchain_core.tools import BaseTool, StructuredTool, tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, create_model
from app.models import Agent
from app.core.agent.tool_adapters import http_tool, python_tool, builtin_tools, rag_tool, workflow_tool

async def build_tools(agent: Agent) -> list[BaseTool]:
    """把 agent 挂载的 tools/skills/mcps/wfs/docs 聚合为 LangChain 工具池"""
    tools: list[BaseTool] = []

    # 1. tools（HTTP/内置/Python）
    for t in await load_tools(agent.tools):
        if t.type == "HTTP":       tools.append(http_tool.to_base_tool(t))
        elif t.type == "Python":   tools.append(await python_tool.to_base_tool(t))
        elif t.type == "内置":      tools.append(builtin_tools.to_base_tool(t))

    # 2. docs → 一个 RAG 检索工具（复用 HybridRetriever）
    if agent.docs:
        tools.append(rag_tool.build_rag_tool(doc_ids=agent.docs, name="search_documents",
                     description="在挂载的文档中检索相关信息"))

    # 3. wfs → 每个工作流一个工具（schema 从 start 节点 input_variables 生成）
    for wf in await load_workflows(agent.wfs):
        tools.append(workflow_tool.build_workflow_tool(wf))

    # 4. mcps → 用 langchain-mcp-adapters 发现工具（Phase2 真客户端）
    for m in await load_mcps(agent.mcps):
        tools.extend(await mcp_tools.load(m))

    # 5. skills → 每个技能一个"激活"工具（注入 skill.prompt 到对话）
    for sk in await load_skills(agent.skills):
        tools.append(skill_activation_tool(sk))

    return tools

def skill_activation_tool(skill) -> BaseTool:
    """技能 = 触发词命中即注入其 prompt。这里暴露为显式工具，agent 可主动激活。"""
    @tool(skill.name, description=f"激活技能：{skill.desc}。触发条件：{skill.trigger}")
    def _activate() -> str:
        return f"[SKILL ACTIVATED]\n{skill.prompt}\n[挂载工具: {skill.tools}]"
    return _activate
```

### 3.4 RAG 工具（复用 chat 的 retriever）

```python
# app/core/agent/tool_adapters/rag_tool.py
from langchain_core.tools import tool
from app.core.retrieval.hybrid_retriever import HybridRetriever
from app.core.scenes import get_scene_config

def build_rag_tool(doc_ids: list[str], name: str, description: str):
    @tool(name, description=description)
    async def search_documents(query: str) -> str:
        """在文档中检索与 query 相关的内容，返回拼接的参考资料。"""
        retriever = HybridRetriever(kb_ids=[], doc_ids=doc_ids,
                                    scene_config=get_scene_config("general"), top_k=5, enable_nav=False)
        docs = await retriever.ainvoke(query)
        return "\n\n".join(f"《{d.metadata['doc_title']}》{d.metadata['node_title']}\n{d.page_content}"
                           for d in docs) or "未找到相关内容"
    return search_documents
```

### 3.5 workflow 作为工具

```python
# app/core/agent/tool_adapters/workflow_tool.py
from langchain_core.tools import StructuredTool
from pydantic import create_model
from app.services.workflow_service import trigger_workflow

def build_workflow_tool(wf):
    """从 workflow start 节点的 input_variables 动态生成工具 schema"""
    input_vars = wf.definition.get("start_inputs", [])   # [{name,type,description}]
    fields = {v["name"]: (str, ...) for v in input_vars}  # 简化为 str
    InputModel = create_model(f"{wf.id}_Input", **fields)

    async def _run(**kwargs) -> str:
        result = await trigger_workflow(wf.id, inputs=kwargs, trigger_type="agent")
        return f"工作流已触发，execution_id={result.execution_id}，状态={result.status}"

    return StructuredTool.from_function(
        coroutine=_run, name=f"workflow_{wf.name}", description=wf.description or wf.name,
        args_schema=InputModel,
    )
```

### 3.6 agent 执行（create_react_agent + 流式）

```python
# app/services/agent_service.py
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver  # Phase2；多实例换 PostgresSaver
from app.providers.langchain_factory import build_chat_model
from app.core.agent.tool_registry import build_tools
from app.sse.emitter import SSE

class AgentService:
    async def chat(self, agent_id: str, question: str, history: list, user) -> AsyncIterator:
        agent = await self._load(agent_id)
        if not agent.enabled:
            yield SSE.error(40300, "智能体未启用"); return

        llm = build_chat_model(use="qa", temperature=agent.temp,
                               max_tokens=int(agent.maxtok) if agent.maxtok else None)
        tools = await build_tools(agent)

        # state_modifier：注入 agent system prompt
        react_app = create_react_agent(model=llm, tools=tools, state_modifier=agent.prompt,
                                       checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": f"agent:{agent_id}:{user.id}"}}

        yield SSE.phase("generate", f"智能体 {agent.name} 思考中...")
        buffer = []
        # astream_events：细粒度流式（tool 调用 + token）
        async for ev in react_app.astream_events(
            {"messages": [("user", question)]}, config=config, version="v2",
        ):
            kind, name = ev["event"], ev["name"]
            if kind == "on_tool_start":
                yield SSE.tool_start(name, ev["data"].get("input"))
            elif kind == "on_tool_end":
                yield SSE.tool_end(name, str(ev["data"].get("output"))[:500])
            elif kind == "on_chat_model_stream":
                token = ev["data"]["chunk"].content
                if token:
                    buffer.append(token)
                    yield SSE.token(token)

        await self._save_message(...)   # 持久化（agent 对话历史）
        yield SSE.done(...)
```

> **记忆**：用 LangGraph `MemorySaver`（进程内）起步，多 worker 后换 `PostgresSaver`（与 workflow 共享 checkpoint 库）。`thread_id` 按 `agent:user` 隔离会话历史。

### 3.7 agent SSE 事件

扩展 chat 的事件集（前端 `types/` 需补 `tool_start`/`tool_end`）：

| event | data | 说明 |
|-------|------|------|
| phase | `{phase, message}` | |
| tool_start | `{tool, input}` | agent 调用工具 |
| tool_end | `{tool, output}` | 工具返回 |
| token | `{token}` | LLM 流式输出 |
| done | `{message_id, agent_id}` | |
| error | `{code, message}` | |

### 3.8 落地 TDD 要点

1. `test_build_tools_aggregates_all_kinds`：构造含 5 类挂载的 agent，断言工具数与类型。
2. `test_rag_tool_returns_context`：mock retriever，验证返回拼接资料。
3. `test_workflow_tool_schema_from_inputs`：验证 args_schema 字段来自 start input_variables。
4. `test_react_agent_streams_tool_events`：mock create_react_agent 的 astream_events，验证 tool_start/tool_end/token 顺序。
5. `test_agent_disabled_returns_error`。

---

## 4. workflow 模块（LangGraph）— Phase2

> 细化主方案 §5.11 + V2_workflow.md。给出 GraphBuilder、12 节点执行器、变量系统、checkpoint、SSE、调试的完整设计。

### 4.1 引擎文件结构

```
app/engine/
├── state.py                      # WorkflowState (TypedDict)
├── graph_builder.py              # definition → CompiledStateGraph
├── node_router.py                # 节点工厂（type → 执行器）
├── variable_resolver.py          # {{node.output.x}} 插值
├── progress_emitter.py           # 节点事件 → SSEBus
├── nodes/
│   ├── base.py                   # BaseNodeExecutor
│   ├── start.py end.py
│   ├── llm_node.py               # 复用 build_chat_model
│   ├── rag_node.py               # 复用 HybridRetriever
│   ├── code_node.py              # Docker 沙箱
│   ├── http_node.py
│   ├── condition_node.py
│   ├── loop_node.py
│   ├── human_node.py             # → workflow_todos + interrupt
│   ├── tool_node.py              # 复用 tool_registry
│   ├── variable_assign.py
│   └── template_render.py        # Jinja2
└── executor.py                   # Celery/ARQ 入口：build + astream + emit
```

### 4.2 WorkflowState

```python
# app/engine/state.py
from typing import TypedDict, Any, Optional
class WorkflowState(TypedDict):
    workflow_id: str
    execution_id: str
    thread_id: str
    user_id: str
    variables: dict              # 全局变量池 workflow.custom.*
    node_outputs: dict           # {node_id: {output:..., error:..., metadata:...}}
    current_node: Optional[str]
    status: str                  # pending/running/paused/completed/failed/cancelled
    error: Optional[str]
    started_at: float
    node_timings: dict
    debug_mode: bool
    loop_stack: list
```

### 4.3 GraphBuilder（definition → StateGraph）

```python
# app/engine/graph_builder.py
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.engine.state import WorkflowState
from app.engine.node_router import NodeRouter

class GraphBuilder:
    def __init__(self, db_conn_str: str): self.conn_str = db_conn_str

    async def build(self, definition: dict, execution_id: str, debug: bool = False):
        nodes = definition["nodes"]; edges = definition["edges"]
        graph = StateGraph(WorkflowState)

        # 1. 注册节点执行器
        for nd in nodes:
            executor = NodeRouter.create(nd)
            graph.add_node(nd["id"], executor.run)

        # 2. 注册边（普通 + 条件）
        for e in edges:
            src, tgt, handle = e["source"], e["target"], e.get("sourceHandle")
            cond = e.get("data", {}).get("condition")
            if cond or (handle and handle not in ("l", "r", "output")):
                # condition 节点的分支：按 sourceHandle 路由
                graph.add_conditional_edges(src, self._branch_fn(handle), {handle: tgt})
            else:
                graph.add_edge(src, tgt)

        # 3. 入口/出口
        start_id = next(n["id"] for n in nodes if n["type"] == "start")
        graph.add_edge(START, start_id)
        for n in nodes:
            if n["type"] == "end": graph.add_edge(n["id"], END)

        # 4. checkpoint + 中断点（debug 暂停所有；human 暂停 human 节点前）
        checkpointer = AsyncPostgresSaver.from_conn_string(self.conn_str)
        await checkpointer.setup()
        interrupt = ["*"] if debug else ["human_*"]
        return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt)

    def _branch_fn(self, handle):
        # 返回固定分支 key 的路由函数
        return lambda state: handle
```

### 4.4 节点执行器基类与工厂

```python
# app/engine/nodes/base.py
from abc import ABC, abstractmethod
class BaseNodeExecutor(ABC):
    def __init__(self, node_def: dict):
        self.node_id = node_def["id"]
        self.node_type = node_def["type"]
        self.config = node_def.get("data", {}).get("config", {})
    @abstractmethod
    async def run(self, state) -> dict: ...   # 返回状态更新
    async def emit(self, execution_id, event: dict): ...

# app/engine/node_router.py
from langchain_core.tools import BaseTool  # noqa
NODE_REGISTRY = {
    "start": StartExecutor, "end": EndExecutor,
    "llm": LLMExecutor, "rag": RAGExecutor, "code": CodeExecutor, "http": HTTPExecutor,
    "condition": ConditionExecutor, "loop": LoopExecutor, "human": HumanExecutor,
    "tool": ToolExecutor, "variable_assign": VariableAssignExecutor,
    "template_render": TemplateRenderExecutor,
    # Phase2+：sub_workflow/parallel/try_catch
}
```

### 4.5 关键节点实现骨架

**LLM 节点**（复用 chat 的 LangChain 抽象）：

```python
# app/engine/nodes/llm_node.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from app.providers.langchain_factory import build_chat_model
from app.engine.variable_resolver import resolve
class LLMExecutor(BaseNodeExecutor):
    async def run(self, state):
        t0 = time.perf_counter()
        model_key = self.config.get("model", "qa")          # fast/generation/custom
        llm = build_chat_model(use=model_key if model_key in ("qa","summary","rewrite") else "qa",
                               temperature=self.config.get("temperature", 0.7),
                               max_tokens=self.config.get("max_tokens"))
        prompt = ChatPromptTemplate.from_messages([
            ("system", resolve(self.config.get("system_prompt",""), state)),
            ("human", resolve(self.config.get("user_prompt","{question}"), state)),
        ])
        chain = prompt | llm | (JsonOutputParser() if self.config.get("output_mode")=="json" else StrOutputParser())
        out = await chain.ainvoke({})
        return {"node_outputs": {**state["node_outputs"], self.node_id: {"output": out}},
                "node_timings": {**state["node_timings"], self.node_id: (time.perf_counter()-t0)*1000}}
```

**RAG 节点**（四端口输出，复用 HybridRetriever）：

```python
# app/engine/nodes/rag_node.py
class RAGExecutor(BaseNodeExecutor):
    async def run(self, state):
        query = resolve(self.config["query"], state)
        retriever = HybridRetriever(kb_ids=[], doc_ids=self.config.get("document_ids",[]),
                                    scene_config=get_scene_config(self.config.get("scene","general")),
                                    top_k=self.config.get("top_k",5),
                                    enable_nav=self.config.get("enable_navigation",True))
        docs = await retriever.ainvoke(query)
        chunks = retriever.last_result.chunks
        citations = build_references(chunks)
        answer = ""
        if self.config.get("generate_answer"):
            gen_llm = build_chat_model(use="qa")
            answer = await (ANSWER_PROMPT | gen_llm | StrOutputParser()).ainvoke(
                {"system_prompt":"...","context":build_context(docs),"history":"","question":query})
        # 四端口：chunks/answer/citations/nav_anchors
        return {"node_outputs": {**state["node_outputs"], self.node_id: {
            "chunks": [d.dict() for d in docs], "answer": answer,
            "citations": citations, "nav_anchors": retriever.last_result.nav_info.anchors if retriever.last_result else []}}}
```

**Code 节点**（Docker 沙箱，Phase2 沙箱池）：

```python
# app/engine/nodes/code_node.py
class CodeExecutor(BaseNodeExecutor):
    async def run(self, state):
        from app.providers.sandbox import run_in_sandbox   # Docker 容器池
        inputs = {k: resolve(v, state) for k,v in self.config.get("input_mapping",{}).items()}
        result = await run_in_sandbox(
            code=self.config["code"], inputs=inputs,
            timeout=self.config.get("timeout_seconds",30),
            memory_mb=self.config.get("memory_limit_mb",256),
            network=self.config.get("network_access",False),
        )
        return {"node_outputs": {**state["node_outputs"], self.node_id: {"output": result.output, "logs": result.logs}}}
```

**Condition 节点**（按 sourceHandle 分支）：

```python
# app/engine/nodes/condition_node.py
class ConditionExecutor(BaseNodeExecutor):
    async def run(self, state):
        # 评估 conditions，把命中的分支 key 写入 state，供 GraphBuilder._branch_fn 路由
        for rule in self.config["conditions"]:
            if self._eval(rule, state): return {"current_node": self.node_id, "_branch": rule["id"]}
        return {"current_node": self.node_id, "_branch": self.config.get("default_branch","else")}
```

**Human 节点**（人工介入 → todos，对齐 §8）：

```python
# app/engine/nodes/human_node.py
class HumanExecutor(BaseNodeExecutor):
    async def run(self, state):
        # interrupt_before=human_* 已暂停 graph；创建待办，恢复时由 TodoService 注入 form_data
        todo = await create_todo(execution_id=state["execution_id"], node_id=self.node_id,
                                 title=self.config["title"], form_schema=self.config["form_schema"],
                                 timeout_hours=self.config.get("timeout_hours",24))
        await ProgressEmitter.emit(state["execution_id"], {"event":"execution_paused","todo_id":str(todo.id)})
        return {"current_node": self.node_id}   # 实际等待 resume
```

### 4.6 变量系统（VariableResolver）

```python
# app/engine/variable_resolver.py
import re
from langchain_core.globals import get_debug
_PATTERN = re.compile(r"\{\{\s*([\w.]+)(?:\[(\d+)\])?(\.\w+)?\s*\}\}")
def resolve(expr: str, state) -> str:
    """解析 {{node_id.output.field}} / {{workflow.custom.x}} / {{loop.item}}"""
    def _sub(m):
        path = m.group(1)
        if path.startswith("workflow.custom."):
            return str(state["variables"].get(path.split(".",2)[-1], ""))
        if path.startswith("loop."):
            return str(state.get("_loop",{}).get(path.split(".",1)[-1], ""))
        nid, field = path.split(".",1) if "." in path else (path,"output")
        out = state["node_outputs"].get(nid, {})
        return str(out.get(field, ""))
    return _PATTERN.sub(_sub, expr or "")
```

### 4.7 执行入口（ARQ task + SSE 推送）

```python
# app/engine/executor.py
async def execute_workflow(ctx, execution_id, workflow_id, inputs, debug=False):
    execution = await load_execution(execution_id)
    definition = await load_published_definition(workflow_id, execution.version)
    builder = GraphBuilder(settings.DATABASE_URL)
    graph = await builder.build(definition, execution_id, debug)
    config = {"configurable": {"thread_id": execution_id}}
    initial = {"workflow_id":workflow_id,"execution_id":execution_id,"thread_id":execution_id,
               "user_id":execution.user_id,"variables":inputs,"node_outputs":{},
               "status":"running","node_timings":{},"debug_mode":debug,"loop_stack":[]}
    await ProgressEmitter.emit(execution_id, {"event":"execution_start","total_nodes":len(definition["nodes"])})
    try:
        async for ev in graph.astream(initial, config=config, stream_mode="updates"):
            for nid, update in ev.items():
                await on_node_update(execution_id, nid, update)   # → node_start/node_complete SSE
        await finish_execution(execution_id, "completed")
        await ProgressEmitter.emit(execution_id, {"event":"execution_complete","success":True})
    except Exception as e:
        await finish_execution(execution_id, "failed", error=str(e))
        await ProgressEmitter.emit(execution_id, {"event":"execution_error","error":str(e)})
```

### 4.8 调试：单步 + 单节点测试

- **单步**：`debug=True` 时 `interrupt_before=["*"]`，每节点前暂停；`POST /executions/:id/debug/continue` 调 `graph.astream(None, config)` 推进一步。
- **单节点测试**：`POST /executions/:id/debug/test-node` 构造 mock state，单独跑 `NodeRouter.create(node_def).run(mock_state)`，返回输出 + 日志（不落库、不影响执行）。

### 4.9 SSE 事件（对齐前端 `types/workflow.ts`）

`execution_start` / `node_start` / `node_progress` / `node_complete` / `node_error` / `execution_paused` / `execution_resumed` / `execution_complete` / `execution_error`。经 `SSEBus`（Redis pub/sub）从 worker 推到持有 SSE 连接的 API 进程。

### 4.10 落地 TDD 要点

1. `test_graph_builder_linear`：start→llm→end 的 definition，验证编译成功且入口正确。
2. `test_condition_routing`：验证条件边按命中分支路由。
3. `test_llm_node_uses_langchain_model`：mock build_chat_model，验证节点调用链。
4. `test_human_node_creates_todo_and_pauses`：验证 interrupt + todo 创建。
5. `test_checkpoint_resume`：人为失败后 resume，验证从断点继续。
6. `test_variable_resolver_paths`：覆盖 node.output / workflow.custom / loop.item 三类路径。

---

## 5. tools 模块（工具系统）— Phase2

> 对齐前端 `types/tool.ts`：Tool(type=HTTP/内置/Python)、ToolParam(n/t/d)、ToolAuth(mode/key)、ToolTestResult。

### 5.1 文件结构

```
app/
├── api/v2/tools.py                    # CRUD + POST /:id/test
├── services/tool_service.py           # CRUD
├── core/tools/
│   ├── executor.py                    # dispatch: HTTP/内置/Python
│   ├── http_executor.py
│   ├── builtin_registry.py            # 内置工具注册表
│   └── sandbox_executor.py            # Python 工具 → Docker 沙箱（与 workflow code 节点共用）
└── core/agent/tool_adapters/http_tool.py / python_tool.py / builtin_tools.py  # → BaseTool（§3.3）
```

### 5.2 执行器

```python
# app/core/tools/http_executor.py
import httpx, time
from app.security.crypto import decrypt
async def execute_http(tool, args: dict) -> dict:
    cfg = tool.config   # {method,url,headers,body_type,body,timeout}
    url = render(cfg["url"], args)
    headers = {**cfg.get("headers",{})}
    if tool.auth and tool.auth.get("mode") != "none":
        key = decrypt(tool.auth["key_enc"]) if tool.auth["mode"] in ("apikey","bearer") else None
        if tool.auth["mode"] == "bearer": headers["Authorization"] = f"Bearer {key}"
        elif tool.auth["mode"] == "apikey": headers["X-API-Key"] = key
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=cfg.get("timeout",30)) as c:
        resp = await c.request(cfg["method"], url, headers=headers,
                               json=args if cfg.get("body_type")=="json" else None)
    return {"success": resp.status_code < 400, "data": safe_parse(resp),
            "error": None if resp.status_code<400 else resp.text, "duration": int((time.perf_counter()-t0)*1000)}

# app/core/tools/builtin_registry.py
BUILTIN = {
    "current_time": lambda args: {"now": datetime.utcnow().isoformat()},
    "string_length": lambda args: {"length": len(args.get("s",""))},
    # 可扩展
}
async def execute_builtin(tool, args): return {"success":True,"data":BUILTIN[tool.name](args),"duration":0}

# app/core/tools/sandbox_executor.py
async def execute_python(tool, args):
    from app.providers.sandbox import run_in_sandbox
    r = await run_in_sandbox(code=tool.config["code"], inputs=args, timeout=30, memory_mb=256, network=False)
    return {"success": r.ok, "data": r.output, "error": r.error, "duration": r.duration}
```

### 5.3 test 接口

```python
# POST /tools/:id/test  body: {args: {param: value,...}}
async def test_tool(id, args):
    tool = await get(id)
    if not tool.enabled: return err(40300, "工具未启用")
    try:
        if tool.type == "HTTP":   r = await execute_http(tool, args)
        elif tool.type == "Python": r = await execute_python(tool, args)
        else: r = await execute_builtin(tool, args)
    except Exception as e:
        r = {"success": False, "error": str(e), "duration": 0}
    return ok(r)   # ToolTestResult
```

### 5.4 → LangChain BaseTool（供 agent/workflow 复用）

```python
# app/core/agent/tool_adapters/http_tool.py
from langchain_core.tools import StructuredTool
from pydantic import create_model
from app.core.tools.executor import execute
def to_base_tool(tool):
    fields = {p["n"]: (str, ...) for p in tool.params}      # ToolParam.n/.t
    ArgsModel = create_model(f"{tool.id}_Args", **fields)
    async def _run(**kwargs): return (await execute(tool, kwargs))["data"]
    return StructuredTool.from_function(coroutine=_run, name=tool.name,
                                        description=tool.desc or tool.name, args_schema=ArgsModel)
```

---

## 6. skills 模块（技能系统）— Phase2

> 对齐前端 `types/skill.ts`：Skill(ico/name/scope/ver/desc/trigger/prompt/tools[]/docs[]/wfs[]/examples/scripts/budget/used)。

### 6.1 定位

技能 = **预设 system prompt + 触发词 + 挂载资源（tools/docs/wfs）**。本质是"快捷加载的 agent 配置片段"。

两种激活方式：
- **显式**：agent 挂载 skill → 作为"激活工具"（§3.3 `skill_activation_tool`），LLM 主动调用注入 prompt。
- **隐式**：chat/agent 对话时，后端按用户输入匹配技能 trigger，命中则把 skill.prompt 注入 system message（类似 system prompt 覆盖/追加），并把 skill 挂载的 tools/docs/wfs 加入本次会话。

### 6.2 隐式触发匹配

```python
# app/services/skill_service.py
async def match_skills(text: str, candidates: list[Skill]) -> list[Skill]:
    """按 trigger 关键词命中（支持逗号分隔多触发词）"""
    hit = []
    for sk in candidates:
        triggers = [t.strip() for t in (sk.trigger or "").split(",") if t.strip()]
        if any(t in text for t in triggers):
            hit.append(sk)
    return hit

async def apply_skills(message: str, skills: list[Skill]):
    """返回 (追加 system_prompt, 额外 doc_ids, 额外 tool_ids)"""
    extra_prompt = "\n\n".join(f"[技能 {s.name}]\n{s.prompt}" for s in skills)
    doc_ids = [d for s in skills for d in s.docs]
    tool_ids = [t for s in skills for t in s.tools]
    return extra_prompt, doc_ids, tool_ids
```

> chat_service（§2.6）可在阶段 1（parse）后调用 `match_skills`，把命中的 skill prompt 拼到 `system_prompt`、把 doc_ids 并入检索范围。

### 6.3 CRUD + duplicate（对齐前端）

```python
GET/POST   /skills
GET/PUT/DELETE /skills/:id        # DELETE：scope==builtin 返回 40300
POST       /skills/:id/duplicate  # 复制为 custom，ver=1.0.0，used=0
```

### 6.4 → LangChain 集成

技能不直接成为 `BaseTool`（它是 prompt 资源），但技能挂载的 tools/docs/wfs 会经 §3.3 的 tool_registry 聚合。技能本身的"激活"通过 `skill_activation_tool`（§3.3）暴露给 agent。

---

## 7. mcp 模块（Model Context Protocol）— Phase2

> 对齐前端 `types/mcp.ts`：Mcp(tp=stdio/SSE, cmd, status=on/off/err, toolCount, env[{k,v}], timeout)。
> 主方案决策 #12：Phase1 配置先行，Phase2 真客户端。

### 7.1 两阶段

| 阶段 | 能力 | test 接口 |
|------|------|----------|
| Phase1（配置先行） | CRUD（存配置，加密 env） | 连通性模拟（不真连，返回固定 mock） |
| Phase2（真客户端） | 真正拉起 MCP server，发现工具，暴露给 agent | 真连 list_tools，返回 toolCount + tools[] |

### 7.2 Phase2 真客户端（基于 langchain-mcp-adapters）

```python
# app/core/agent/tool_adapters/mcp_tools.py
from langchain_mcp_adapters.client import MultiServerMCPClient
from app.security.crypto import decrypt
from app.models import Mcp

_connections: dict[str, MultiServerMCPClient] = {}   # 进程内连接池

async def get_client(mcp: Mcp) -> MultiServerMCPClient:
    if mcp.id in _connections: return _connections[mcp.id]
    env = {e["k"]: decrypt(e["v_enc"]) for e in mcp.env} if mcp.env else None
    server = {
        "transport": mcp.tp,                    # "stdio" | "sse"
        "command": mcp.cmd.split()[0] if mcp.tp=="stdio" else None,
        "args": mcp.cmd.split()[1:] if mcp.tp=="stdio" else None,
        "url": mcp.cmd if mcp.tp=="sse" else None,
        "env": env,
        "timeout": mcp.timeout,
    } if mcp.tp == "stdio" else {"transport":"sse","url":mcp.cmd,"timeout":mcp.timeout}
    client = MultiServerMCPClient({"mcp": server})
    _connections[mcp.id] = client
    return client

async def load(mcp: Mcp) -> list:
    """发现 MCP server 暴露的工具，返回 LangChain BaseTool 列表"""
    client = await get_client(mcp)
    return await client.get_tools()   # langchain-mcp-adapters 返回标准 BaseTool

async def test(mcp: Mcp) -> dict:
    """POST /mcps/:id/test：真连 + list_tools"""
    try:
        client = await get_client(mcp)
        tools = await client.get_tools()
        await update_mcp_status(mcp.id, "on", tool_count=len(tools))
        return {"success": True, "toolCount": len(tools), "tools": [t.name for t in tools], "duration": 0}
    except Exception as e:
        await update_mcp_status(mcp.id, "err", tool_count=0)
        return {"success": False, "toolCount": 0, "error": str(e), "duration": 0}
```

> **生命周期**：stdio 模式下 `MultiServerMCPClient` 维护子进程；连接池缓存避免重复拉起。进程退出/异常时清理子进程。

### 7.3 与 agent/workflow 集成

- agent：`tool_registry.build_tools`（§3.3）遍历 `agent.mcps` → `mcp_tools.load(mcp)` → 注入工具池。
- workflow：`tool` 节点选择 MCP 工具时，从对应 mcp 的工具池取。

### 7.4 CRUD + test（对齐前端）

```python
GET/POST       /mcps
GET/PUT/DELETE /mcps/:id
POST           /mcps/:id/test    # Phase1 mock / Phase2 真连
```

---

## 8. todos 模块（人工介入待办）— Phase2

> 对齐前端 `types/todo.ts`：Todo(title/source/status=pending|done|rejected/submittedAt/cd/deadline/formSchema/formData)、FormField(key/label/type/required/options)。
> 与 workflow `human` 节点强耦合（§4.5）。

### 8.1 数据来源

待办**只由 workflow `human` 节点产生**（`HumanExecutor.run` 创建，§4.5）。无人工创建入口（前端 todo 页是只读 + 处理）。

### 8.2 处理流程

```
workflow 执行到 human 节点
  → interrupt_before=human_* 暂停 graph
  → 创建 workflow_todos(status=pending, form_schema, deadline)
  → SSE execution_paused 事件（前端 todos 页刷新看到新待办）

用户在前端 /todos 点击处理
  → GET /todos/:id（取 form_schema 渲染动态表单）
  → POST /todos/:id/submit {form_data}
      → 写 form_data, status=done, submitted_at
      → 注入 form_data 到 WorkflowState.human_input
      → graph.astream(None, config) 恢复执行（resume）
      → SSE execution_resumed
  或 POST /todos/:id/reject
      → status=rejected
      → workflow 按 timeout_action=fail 终止（或 skip 继续）
```

### 8.3 Service

```python
# app/services/todo_service.py
async def list(status: str | None, user):
    q = select(Todo).where(...按照权限...)
    if status == "pending": q = q.where(Todo.status=="pending")
    elif status == "done": q = q.where(Todo.status.in_(["done","rejected"]))
    todos = await db.execute(q)
    return [serialize_with_deadline(t) for t in todos]   # 计算 cd/deadline 剩余秒

async def submit(todo_id, form_data, user):
    todo = await get(todo_id)
    if todo.status != "pending": return err(40010, "待办已处理")
    await db.update(todo, status="done", form_data=form_data, submitted_at=now())
    # 恢复对应 workflow 执行
    await resume_workflow(todo.execution_id, node_id=todo.node_id, human_input=form_data)
    return ok({"todo_id":str(todo.id),"status":"done","execution_resumed":True})

async def reject(todo_id, user):
    todo = await get(todo_id)
    await db.update(todo, status="rejected")
    await fail_or_skip_execution(todo.execution_id, todo.node_id, action="fail")
    return ok({"todo_id":str(todo.id),"status":"rejected"})

async def resume_workflow(execution_id, node_id, human_input):
    """从 checkpoint 恢复，注入 human_input"""
    graph = await GraphBuilder(settings.DATABASE_URL).build(definition, execution_id)
    config = {"configurable":{"thread_id":execution_id}}
    # 把 human_input 写入 checkpoint state 后 astream(None)
    await graph.aupdate_state(config, {"human_input": human_input, "status":"running"})
    enqueue_task("execute_workflow_resume", execution_id)   # ARQ 异步推进 + SSE
```

### 8.4 超时处理

```python
# ARQ 周期任务（类 cron，每分钟）
async def check_todo_timeout(ctx):
    expired = await db.fetch_all("SELECT * FROM workflow_todos WHERE status='pending' AND deadline<NOW()")
    for t in expired:
        await db.update(t, status="timeout" if t.timeout_action=="skip" else "failed_marker")
        if t.timeout_action == "skip": await resume_workflow(t.execution_id, t.node_id, {})
        else: await fail_execution(t.execution_id, f"Human timeout: {t.title}")
```

### 8.5 端点（对齐前端 `api/todo.ts`）

```python
GET  /todos?status=pending|done
GET  /todos/:id
POST /todos/:id/submit     # {form_data}
POST /todos/:id/reject
```

### 8.6 落地 TDD 要点

1. `test_human_node_creates_pending_todo`：跑 workflow 到 human 节点，断言 todo 创建 + status=pending。
2. `test_submit_resumes_execution`：submit 后断言 execution 状态恢复 running 且 human_input 注入。
3. `test_reject_fails_execution`。
4. `test_timeout_skip_vs_fail`：模拟 deadline 过期，验证 skip 继续 / fail 终止。
5. `test_list_filter_by_status`。

---

## 9. settings 模块增强 — Phase1(基础) / Phase2(完善)

> 对齐前端 `types/settings.ts`：ModelDef(name/prov/use/temp/ctx/dim/def/url/key/params)、ModelGroup(llm/embed/rerank)、Scene(id/name/description/config{chunk_size,top_k,system_prompt})、PROVIDERS(dashscope/openai/ollama/azure/vllm)。

### 9.1 model_configs 多 provider 多用途

Phase1 已建表 + provider 抽象（主方案 §5.2）。Phase2 完善：

```python
# app/api/v2/settings.py
GET    /settings/models                     # 全部模型（按 grp 分组）
GET    /settings/models?group=llm           # 指定分组
POST   /settings/models?group=llm           # 新增/更新（同名 upsert）
PUT    /settings/models/:group/default?name=xxx   # 同组互斥设默认
DELETE /settings/models?group=llm&name=xxx   # 删除
```

**用途（use）维度**（对齐前端 USE_OPTIONS）：
- llm 组：`qa`(答疑生成) / `summary`(快速摘要) / `rewrite`(问题改写)
- embed 组：`retrieval`(向量召回)
- rerank 组：`rerank`(精排)

> `build_chat_model(use)`（§1.2）按 use 取默认模型——**settings 页改默认模型即实时切换 chat/agent/workflow 的实际调用模型**，零代码改动。

### 9.2 scenes 检索场景 CRUD

```python
GET/POST       /settings/scenes
GET/PUT/DELETE /settings/scenes/:id
```

SceneConfig 字段（核心算法读取）：`chunk_size, chunk_overlap, top_k, vector_top_k, trgm_top_k, vector_weight, keyword_weight, rrf_k, rerank_enabled, rerank_threshold, rerank_top_n, navigation_enabled, nav_confidence_threshold, system_prompt`。

内置场景（`scenes` 表 `built_in=true`）：general / bidding / contract / tech / product（对齐前端 chat scenes）。

### 9.3 与 LangChain 桥接

settings 是**唯一配置真相源**，LangChain 通过 `langchain_factory`（§1.2）消费它。settings 页面 ≠ LangChain 直连，而是经我们加密存储 + 工厂构造。

---

## 10. Phase 3：生产化

### 10.1 多用户与 RBAC

```python
# users 表 role: admin / editor / viewer
# 所有业务表带 user_id；查询统一注入 owner 过滤
# projects 表（Phase3）：项目级资源聚合 + 成员共享
#   knowledge_bases/workflows/documents 带 project_id（可空=私有）
#   project_members(project_id, user_id, role)
```

- Phase1 单用户 → Phase2 注册/登录/数据隔离 → Phase3 项目级共享 + 角色权限。
- 中间件 `get_current_user` + 资源所有权校验（`_check_owner(resource, user)`）。

### 10.2 存储切换（本地 FS → MinIO/OSS）

```python
# app/providers/storage/factory.py
def get_storage() -> ObjectStorage:
    if settings.STORAGE_TYPE == "minio":
        from app.providers.storage.minio_impl import MinioStorage
        return MinioStorage(settings.MINIO_ENDPOINT, settings.MINIO_ACCESS_KEY, settings.MINIO_SECRET_KEY, settings.MINIO_BUCKET)
    return LocalFSStorage(settings.STORAGE_LOCAL_DIR)
```

切换只需改 `.env` 的 `STORAGE_TYPE=minio` + MinIO 配置，业务代码（经 ObjectStorage 接口）零改动。

### 10.3 LangSmith 全链路

Phase1 已埋（§1.3，环境变量启用）。Phase3 配置生产 project、采样率、告警阈值，对话/agent/workflow 的 LLM 调用全链路 trace 可在 LangSmith 看板检索。

### 10.4 性能与压测

| 指标 | 目标 | 工具 |
|------|------|------|
| 对话并发 | 20 QPS P95 延迟不超标 | locust / k6 |
| 检索 | P95 < 300ms | pgvector EXPLAIN 调优 ivfflat lists |
| 文档解析 | 500 页 PDF 正常 | ARQ 并发 worker 扩展 |

多 worker：`uvicorn --workers N` + SSE 切 Redis pub/sub 总线（接口不变，§5.10）。

### 10.5 安全加固

- HTTPS（Nginx + Let's Encrypt）
- 速率限制（slowapi / Nginx limit_req）：登录、对话、上传
- 审计日志（upload/delete/chat 操作落库）
- 密钥轮换（model_configs.api_key 加密 + 可更新）
- 文件 magic number 校验 + 病毒扫描（可选）

### 10.6 运维

- 数据库：每日 `pg_dump` + WAL 归档
- 文件：MinIO 纠删码 / OSS 版本
- 监控：`/health`（DB/Redis/Storage）+ LangSmith 指标
- 故障恢复：ARQ 任务重试 + 手动 resume

---

## 11. 各模块落地路线（TDD plan 索引）

> 本设计文档是 spec。各模块落地时按 **writing-plans** 产出逐步骤 TDD plan，保存到 `docs/superpowers/plans/`。按依赖顺序：

| 顺序 | 模块 | 依赖 | TDD plan 文件 | 预估 |
|------|------|------|--------------|------|
| 1 | **chat（LangChain 重构）** | provider 抽象、retrieval 管线 | `2026-XX-XX-chat-langchain.md` | 5 天 |
| 2 | **settings 完善** | model_configs/scenes | `2026-XX-XX-settings.md` | 1.5 天 |
| 3 | **workflow 引擎** | chat 的 retriever/llm 抽象 | `2026-XX-XX-workflow-langgraph.md` | 8 天 |
| 4 | **tools** | 沙箱 | `2026-XX-XX-tools.md` | 2 天 |
| 5 | **mcp 真客户端** | langchain-mcp-adapters | `2026-XX-XX-mcp.md` | 2 天 |
| 6 | **skills** | — | `2026-XX-XX-skills.md` | 1.5 天 |
| 7 | **agents（LangChain）** | tools/mcp/workflow/skills | `2026-XX-XX-agents-langchain.md` | 3 天 |
| 8 | **todos** | workflow human 节点 | `2026-XX-XX-todos.md` | 2 天 |
| 9 | **Phase3 生产化** | 全模块 | `2026-XX-XX-phase3-prod.md` | 8 天 |

每个 TDD plan 遵循 writing-plans 模板：header（goal/architecture/tech stack）→ 文件结构 → bite-sized tasks（write failing test → run fail → implement → run pass → commit）→ 无占位符 → 自审。

**立即可启动**：顺序 1（chat LangChain 重构）——它属于 Phase1 核心闭环，且 §2 已给出完整代码骨架与 TDD 要点（§2.7），可直接展开为逐步骤 plan。

---

## 附录 A：LangChain 1.X 关键 API 速查

```python
# 模型构造（统一）
from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
llm = init_chat_model(model="qwen-plus", model_provider="openai", base_url=URL, api_key=KEY, temperature=0.3)
emb  = init_embeddings(model="text-embedding-v3", model_provider="openai", base_url=URL, api_key=KEY, dimensions=1024)

# LCEL 组合
chain = prompt | llm | StrOutputParser()
out = await chain.ainvoke({...})
async for token in chain.astream({...}): ...           # 流式

# 检索（自定义）
from langchain_core.retrievers import BaseRetriever
class MyRetriever(BaseRetriever):
    async def _aget_relevant_documents(self, query, *, run_manager): return [Document(...)]
docs = await retriever.ainvoke(query)

# 工具
from langchain_core.tools import tool, StructuredTool, BaseTool
@tool("name", description="...")
async def my_tool(arg: str) -> str: ...

# Agent（react）
from langgraph.prebuilt import create_react_agent
app = create_react_agent(model=llm, tools=tools, state_modifier=SYS_PROMPT, checkpointer=MemorySaver())
async for ev in app.astream_events({"messages":[("user",q)]}, config={"configurable":{"thread_id":TID}}, version="v2"): ...

# 工作流（StateGraph）
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
g = StateGraph(State); g.add_node(id, fn); g.add_edge(a,b); g.add_conditional_edges(src, router_fn, mapping)
app = g.compile(checkpointer=AsyncPostgresSaver.from_conn_string(URL), interrupt_before=["human_*"])

# MCP
from langchain_mcp_adapters.client import MultiServerMCPClient
client = MultiServerMCPClient({"mcp":{"transport":"stdio","command":...,"args":...,"env":...}})
tools = await client.get_tools()

# Tracing：可切换，见 §1.3（TRACING_PROVIDER = langsmith | langfuse | none）
```

## 附录 B：前端契约补充（Phase2 新增端点）

| 端点 | 说明 | 前端需补 |
|------|------|---------|
| `POST /agents/:id/chat` (SSE) | agent 对话，事件含 tool_start/tool_end | agent 对话 UI + types 补 tool 事件 |
| agent/workflow SSE `tool_start`/`tool_end` 事件 | 见 §3.7 / §4.9 | types/chat.ts、workflow.ts 补 |

其余 Phase2 端点（CRUD）前端 `api/*.ts` 已全 mock，后端实现即可对齐，无需前端改动。

---

## 文档版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| V1.0 | 2026-08-08 | 补齐 Phase2/3 全模块详细设计；chat/agents 改用 LangChain 1.X；tracing 默认 LangSmith |

---

*— 文档结束 —*

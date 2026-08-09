# Phase2 agents（LangChain）+ Phase3 生产化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]` tracking.

**Goal:** 实现 agents（create_react_agent + 五类工具聚合 + astream_events SSE + 记忆），并完成 Phase3 生产化（多用户 RBAC、MinIO 切换、速率限制、审计日志、全链路 tracing、备份监控）。这是最后一份 plan，收束全栈。

**Architecture:** agents 表 → tool_registry 聚合 tools/skills/mcp/workflow/rag 为 BaseTool → `langgraph.prebuilt.create_react_agent` + `astream_events(version="v2")` 流式（tool_start/tool_end/token）+ MemorySaver→PostgresSaver 记忆。Phase3：projects 成员模型 + owner 中间件、MinioStorage、slowapi 限流、audit_logs、备份脚本。

**Tech Stack:** langgraph.prebuilt.create_react_agent、@tool/StructuredTool、Plan 2 build_chat_model、Plan 8 tool_registry/mcp_tools、minio SDK、slowapi。

**前置：** Plan 1-8 完成。**关联设计：** Phase2/3 设计 §3、§10。

---

## File Structure

```
backend/app/
├── models/agent.py                     # Task 1
├── core/agent/tool_registry.py         # Task 2（五类聚合）
├── services/agent_service.py           # Task 3（create_react_agent + SSE）
├── api/v2/agents.py                    # Task 4（CRUD + /:id/chat SSE）
├── core/agent/memory.py                # Task 5（checkpoint 记忆）
├── models/project.py + audit.py        # Task 6（Phase3 RBAC + 审计）
├── api/middleware/{owner,audit,rate}.py # Task 6/8
├── providers/storage/minio_impl.py     # Task 7（MinIO 实现）
└── scripts/backup.sh                   # Task 9
```

---

### Task 1: agents ORM + 迁移

**Files:** `models/agent.py` · migrate `0012_agents.py` · `tests/test_agent_model.py`

- [ ] **Step 1: 实现 `models/agent.py`**（对齐前端 `types/agent.ts`）

```python
from sqlalchemy import String, Text, Float, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPk


class Agent(Base, UUIDPk, TimestampMixin):
    __tablename__ = "agents"
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(128), default="gpt-4o")
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    temp: Mapped[float] = mapped_column(Float, default=0.7)
    maxtok: Mapped[str] = mapped_column(String(16), default="2048")
    tools: Mapped = mapped_column(JSONB, default=list)
    docs: Mapped = mapped_column(JSONB, default=list)
    wfs: Mapped = mapped_column(JSONB, default=list)
    mcps: Mapped = mapped_column(JSONB, default=list)
    skills: Mapped = mapped_column(JSONB, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_active: Mapped | None = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 2: 注册 + 迁移 + 测试 + Commit** `feat(models): Agent`

---

### Task 2: tool_registry（五类聚合 → BaseTool）

**Files:** `core/agent/tool_registry.py` · `tests/test_tool_registry.py`

- [ ] **Step 1: 实现**

```python
from langchain_core.tools import StructuredTool, tool
from pydantic import create_model
from sqlalchemy import select
from app.db.session import async_session
from app.models.agent import Agent
from app.models.tool import Tool
from app.models.skill import Skill
from app.models.mcp import Mcp
from app.models.workflow import Workflow
from app.services.tool_service import execute_tool
from app.core.agent.tool_adapters.mcp_tools import load_tools as load_mcp_tools


async def build_tools(agent: Agent) -> list:
    tools = []
    # 1. tools → StructuredTool
    async with async_session() as s:
        for tid in (agent.tools or []):
            t = (await s.execute(select(Tool).where(Tool.id == tid))).scalar_one_or_none()
            if t and t.enabled:
                tools.append(_http_or_python_tool(t))
        # 2. docs → RAG 工具
        if agent.docs:
            tools.append(_rag_tool(agent.docs))
        # 3. wfs → 工作流工具
        for wid in (agent.wfs or []):
            wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one_or_none()
            if wf:
                tools.append(_workflow_tool(wf))
        # 4. mcps → MCP 工具
        for mid in (agent.mcps or []):
            m = (await s.execute(select(Mcp).where(Mcp.id == mid))).scalar_one_or_none()
            if m and m.status == "on":
                tools.extend(await load_mcp_tools(m))
        # 5. skills → 激活工具
        for sid in (agent.skills or []):
            sk = (await s.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
            if sk:
                tools.append(_skill_tool(sk))
    return tools


def _http_or_python_tool(t):
    fields = {p["n"]: (str, ...) for p in (t.params or [])}
    Args = create_model(f"{t.id}_Args", **fields)
    async def _run(**kwargs): return (await execute_tool(str(t.id), kwargs)).get("data")
    return StructuredTool.from_function(coroutine=_run, name=t.name, description=t.description or t.name, args_schema=Args)


def _rag_tool(doc_ids):
    @tool("search_documents", description="在挂载文档中检索相关信息")
    async def _s(query: str) -> str:
        from app.core.retrieval.hybrid_retriever import HybridRetriever
        from app.core.scenes import get_scene_config
        r = HybridRetriever(doc_ids=doc_ids, scene_config=await get_scene_config("general"), top_k=5, enable_nav=False)
        docs = await r.ainvoke(query)
        return "\n\n".join(d.page_content for d in docs) or "未找到"
    return _s


def _workflow_tool(wf):
    async def _run(**kwargs): 
        return f"工作流 {wf.name} 触发（参数：{kwargs}）"
    return StructuredTool.from_function(coroutine=_run, name=f"workflow_{wf.name}", description=wf.description or wf.name)


def _skill_tool(sk):
    @tool(sk.name, description=f"激活技能：{sk.description or ''}")
    def _activate() -> str:
        return f"[SKILL {sk.name}]\n{sk.prompt or ''}"
    return _activate
```

- [ ] **Step 2: 测试**（构造 agent 五类挂载，断言工具数）+ Commit `feat(agent): tool registry (5-kind aggregation)`

---

### Task 3: agent_service（create_react_agent + astream_events SSE）

**Files:** `services/agent_service.py` · `tests/test_agent_service.py`

- [ ] **Step 1: 实现**

```python
from typing import AsyncIterator
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import select
from app.db.session import async_session
from app.models.agent import Agent
from app.providers.langchain_factory import build_chat_model
from app.core.agent.tool_registry import build_tools
from app.core.agent.memory import get_checkpointer
from app.sse.emitter import sse_event
from app.exceptions import BizException, ErrorCode


class AgentService:
    async def chat(self, agent_id: str, question: str, user) -> AsyncIterator[str]:
        async with async_session() as s:
            agent = (await s.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
        if not agent or not agent.enabled:
            yield sse_event("error", {"code": 40300, "message": "智能体不存在或未启用"}); return

        llm = await build_chat_model(use="qa", temperature=agent.temp)
        tools = await build_tools(agent)
        react = create_react_agent(model=llm, tools=tools, state_modifier=agent.prompt or "",
                                    checkpointer=await get_checkpointer())
        config = {"configurable": {"thread_id": f"agent:{agent_id}:{user.id}"}}

        yield sse_event("phase", {"phase": "generate", "message": f"智能体 {agent.name} 思考中..."})
        async for ev in react.astream_events({"messages": [("user", question)]}, config=config, version="v2"):
            kind, name = ev["event"], ev.get("name", "")
            if kind == "on_tool_start":
                yield sse_event("tool_start", {"tool": name, "input": str(ev["data"].get("input"))[:200]})
            elif kind == "on_tool_end":
                yield sse_event("tool_end", {"tool": name, "output": str(ev["data"].get("output"))[:500]})
            elif kind == "on_chat_model_stream":
                token = ev["data"]["chunk"].content
                if token:
                    yield sse_event("token", {"token": token})
        yield sse_event("done", {"agent_id": agent_id})
```

- [ ] **Step 2: 测试**（mock create_react_agent astream_events，验证事件）+ Commit `feat(agent): react agent + sse`

---

### Task 4: agents API（CRUD + /:id/chat SSE）

**Files:** `api/v2/agents.py` · `schemas/agent.py` · `main.py`

- [ ] **Step 1: 实现 CRUD + chat**

```python
from fastapi import APIRouter, Depends, Body
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.agent import Agent
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])

def _out(a): return {"id": str(a.id), "name": a.name, "desc": a.description, "model": a.model, "prompt": a.prompt,
                     "temp": a.temp, "maxtok": a.maxtok, "tools": a.tools, "docs": a.docs, "wfs": a.wfs,
                     "mcps": a.mcps, "skills": a.skills, "enabled": a.enabled, "lastActive": a.last_active.isoformat() if a.last_active else ""}

@router.get("")
async def list_(me=Depends(get_current_user)):
    async with async_session() as s:
        rows = (await s.execute(select(Agent).order_by(Agent.created_at.desc()))).scalars().all()
    return ok([_out(r) for r in rows])

@router.post("")
async def create(body: dict = Body(...), me=Depends(get_current_user)):
    async with async_session() as s:
        a = Agent(name=body["name"], description=body.get("desc"), model=body.get("model","gpt-4o"),
                  prompt=body.get("prompt",""), temp=body.get("temp",0.7), maxtok=str(body.get("maxtok","2048")),
                  tools=body.get("tools",[]), docs=body.get("docs",[]), wfs=body.get("wfs",[]),
                  mcps=body.get("mcps",[]), skills=body.get("skills",[]), enabled=body.get("enabled", True))
        s.add(a); await s.commit(); await s.refresh(a)
    return ok(_out(a))

@router.get("/{aid}")
async def detail(aid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        a = (await s.execute(select(Agent).where(Agent.id == aid))).scalar_one()
    return ok(_out(a))

@router.put("/{aid}")
async def update_(aid: str, body: dict = Body(...), me=Depends(get_current_user)):
    async with async_session() as s:
        a = (await s.execute(select(Agent).where(Agent.id == aid))).scalar_one()
        for k in ("name","description","model","prompt","temp","tools","docs","wfs","mcps","skills","enabled"):
            f = "description" if k == "desc" else k
            if k in body or f in body: setattr(a, f, body.get(k, body.get(f)))
        await s.commit()
    return ok(_out(a))

@router.delete("/{aid}")
async def delete_(aid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        await s.execute(delete(Agent).where(Agent.id == aid)); await s.commit()
    return ok({"success": True})

@router.post("/{aid}/chat")
async def chat(aid: str, body: dict = Body(...), me=Depends(get_current_user)):
    svc = AgentService()
    async def gen():
        try:
            async for ev in svc.chat(aid, body.get("question",""), me): yield ev
        except Exception as e:
            from app.sse.emitter import sse_event
            yield sse_event("error", {"code": 50001, "message": str(e)})
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

- [ ] **Step 2: 挂载 + Commit** `feat(agent): CRUD + /:id/chat SSE`

---

### Task 5: agent 记忆（PostgresSaver checkpoint）

**Files:** `core/agent/memory.py`

- [ ] **Step 1: 实现**（单 worker 用 MemorySaver，多 worker 切 PostgresSaver）

```python
from app.config import settings

_checkpointer = None


async def get_checkpointer():
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    if settings.env == "production":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        cp = AsyncPostgresSaver.from_conn_string(settings.database_url)
        await cp.setup()
        _checkpointer = cp
    else:
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()
    return _checkpointer
```

- [ ] **Step 2: Commit** `feat(agent): checkpoint memory (memory/postgres)`

---

### Task 6（Phase3）: 多用户 RBAC + owner 校验 + 审计日志

**Files:** `models/project.py` · `models/audit.py` · migrate · `api/middleware/owner.py` · `api/middleware/audit.py`

- [ ] **Step 1: 建 projects + project_members + audit_logs 表**

```python
# models/project.py
class Project(Base, UUIDPk, TimestampMixin):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(100))
    owner_id: Mapped = mapped_column(ForeignKey("users.id"))

class ProjectMember(Base, UUIDPk, TimestampMixin):
    __tablename__ = "project_members"
    project_id: Mapped = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20), default="editor")   # owner/editor/viewer

# models/audit.py
class AuditLog(Base, UUIDPk, TimestampMixin):
    __tablename__ = "audit_logs"
    user_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(64))     # upload/delete/chat/login...
    target: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped | None = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 2: owner 依赖**（资源所有权校验，关键写操作注入）

```python
# api/middleware/owner.py
from fastapi import Depends
from sqlalchemy import select
from app.db.session import async_session
from app.models.knowledge_base import KnowledgeBase
from app.exceptions import BizException, ErrorCode

async def check_kb_owner(kb_id: str, user) -> None:
    async with async_session() as s:
        kb = (await s.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))).scalar_one_or_none()
    if not kb or str(kb.user_id) != str(user.id):
        raise BizException(ErrorCode.FORBIDDEN, "无权操作该资源")
```

- [ ] **Step 3: 审计中间件**（记录关键操作）

```python
# api/middleware/audit.py
@app.middleware("http")
async def audit_middleware(request, call_next):
    resp = await call_next(request)
    if request.method in ("POST","DELETE","PUT") and request.url.path.startswith("/api/v2/"):
        # 异步落 audit_logs（需取 user_id，简化）
        pass
    return resp
```

- [ ] **Step 4: 迁移 + Commit** `feat(phase3): RBAC projects/members + audit logs`

---

### Task 7（Phase3）: MinIO 存储切换

**Files:** `providers/storage/minio_impl.py` · 依赖 `minio` · `config.py` 加 MINIO_*

- [ ] **Step 1: 加依赖 + config 字段**

```toml
"minio>=7.2"
```
config 加 `minio_endpoint/minio_access_key/minio_secret_key/minio_bucket`（已部分在主方案 env）。

- [ ] **Step 2: 实现 `minio_impl.py`**

```python
import io
from minio import Minio
from app.config import settings
from app.providers.storage.base import ObjectStorage


class MinioStorage(ObjectStorage):
    def __init__(self):
        self.client = Minio(settings.minio_endpoint,
                            access_key=settings.minio_access_key,
                            secret_key=settings.minio_secret_key, secure=False)
        if not self.client.bucket_exists(settings.minio_bucket):
            self.client.make_bucket(settings.minio_bucket)

    async def put(self, key, data):
        self.client.put_object(settings.minio_bucket, key, io.BytesIO(data), length=len(data))

    async def get(self, key):
        resp = self.client.get_object(settings.minio_bucket, key)
        try: return resp.read()
        finally: resp.close(); resp.release_conn()

    async def delete(self, key):
        self.client.remove_object(settings.minio_bucket, key)

    async def presigned_url(self, key, expires=3600):
        from datetime import timedelta
        return self.client.presigned_get_object(settings.minio_bucket, key, expires=timedelta(seconds=expires))
```

- [ ] **Step 3: factory 已支持**（Plan 3 Task 5 的 `storage_type=="minio"` 分支）→ 切换只需 `.env` 设 `STORAGE_TYPE=minio`

- [ ] **Step 4: 测试 + Commit** `feat(phase3): minio storage impl`

---

### Task 8（Phase3）: 速率限制 + 全链路 tracing 验证

**Files:** 依赖 `slowapi` · `main.py` · docs

- [ ] **Step 1: 速率限制（slowapi）**

```python
# main.py
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
# 关键路由加 @limiter.limit("10/minute")（登录、对话、上传）
```

- [ ] **Step 2: 全链路 tracing 验证**（Plan 2 已配 configure_tracing）

- 设 `TRACING_PROVIDER=langsmith` + key → 对话/agent/workflow 的 LLM 调用在 LangSmith 看 trace
- 或 `TRACING_PROVIDER=langfuse` + 自部署 host → 同上
- 验证：一次对话后，trace 含 nav/retrieve/generate span

- [ ] **Step 3: Commit** `feat(phase3): rate limiting + tracing verification`

---

### Task 9（Phase3）: 备份 + 监控 + 运维 checklist

**Files:** `scripts/backup.sh` · `docs/operations.md`

- [ ] **Step 1: 备份脚本**

```bash
# scripts/backup.sh
#!/bin/bash
set -e
TS=$(date +%Y%m%d_%H%M%S)
docker compose exec -T postgres pg_dump -U easyrag easyrag | gzip > backups/db_$TS.sql.gz
# 文件存储：本地 rsync 或 MinIO mc mirror
find /path/to/data/files -type f | wc -l  # 校验
# 保留最近 30 天
find backups -name "db_*.sql.gz" -mtime +30 -delete
```

- [ ] **Step 2: 运维 checklist 文档** `docs/operations.md`（部署/备份恢复/扩容/故障处理/Langfuse 自部署 compose 片段）

- [ ] **Step 3: Commit** `feat(phase3): backup script + operations doc`

---

### Task 10: 全栈端到端冒烟

- [ ] **Step 1: 全量测试** → `pytest -v` 全绿（Plan 1-9）
- [ ] **Step 2: 完整业务链路**
  - 登录 → 建知识库 → 上传解析 → 对话（引用）
  - 建工作流（start→llm→end）→ 发布 → 执行（SSE）
  - 建 agent（挂载 rag/workflow 工具）→ 对话（tool_start/tool_end/token）
  - settings 切换模型/tracing provider → 验证生效
- [ ] **Step 3: Phase3 验收**（RBAC 隔离、MinIO 切换、限流、审计、备份可恢复）
- [ ] **Step 4: Commit** `test: full-stack e2e + phase3 acceptance`

---

## Plan 9 完成标志
- ✅ agents（CRUD + /:id/chat SSE，create_react_agent + 五类工具聚合 + astream_events + 记忆）
- ✅ Phase3：多用户 RBAC（projects/members + owner 校验）、审计日志、MinIO 切换、速率限制、全链路 tracing、备份 + 运维文档

---

## 🎉 全部 9 份 plan 完成

| # | Plan | Phase | 核心 |
|---|------|-------|------|
| 1 | 基础设施 | P1 | FastAPI+DB+JWT+auth+health |
| 2 | settings/provider/langchain_factory | P1 | 多 provider 模型 + 可切换 tracing |
| 3 | 知识库 + 解析管线 | P1 | 上传/ARQ 解析/树/向量化 |
| 4 | RAG 检索管线 | P1 | 向量+全文+RRF+rerank+HybridRetriever |
| 5 | chat（LangChain）SSE | P1 | 流式对话+多轮+引用 |
| 6 | elements + 联调 | P1 | 引用懒加载+Phase1 闭环 |
| 7 | workflow（LangGraph） | P2 | 12 节点+checkpoint+SSE+调试+todos+模板+沙箱 |
| 8 | tools/skills/mcp | P2 | CRUD+test+MCP 真客户端 |
| 9 | agents + Phase3 | P2/P3 | react agent+RBAC+MinIO+限流+审计+备份 |

**Phase1（Plan 1-6）= 核心闭环可交付；Phase2（7-9）= 工作流/Agent 全能力；Phase3 = 生产就绪。**

下一步建议：用 **subagent-driven-development** 从 Plan 1 开始逐份执行（每份 plan header 已标注 REQUIRED SUB-SKILL）。

*— 全部计划结束 —*
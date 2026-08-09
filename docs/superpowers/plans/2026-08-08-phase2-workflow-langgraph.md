# Phase2 workflow（LangGraph）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]` tracking.

**Goal:** 实现通用工作流编排引擎——definition JSON → LangGraph StateGraph，12 种节点执行器，变量系统，checkpoint 断点续跑，SSE 进度推送，版本快照，调试（单步/单节点测试），人工介入（todos），模板系统。

**Architecture:** LangGraph StateGraph + AsyncPostgresSaver（checkpoint）+ ARQ（异步执行）+ SSEBus（Redis pub/sub 推进度）。节点执行器复用 Plan 2 build_chat_model / Plan 4 HybridRetriever / Plan 6 沙箱引用。GraphBuilder 把前端 definition（nodes/edges，Vue Flow 格式）编译为带条件边的 StateGraph。

**Tech Stack:** langgraph（StateGraph/START/END/compile）、langgraph-checkpoint-postgres（AsyncPostgresSaver）、ARQ、Redis pub/sub、Jinja2（template_render）、Plan 1-6 基础。

**前置：** Plan 1-6 完成。**关联设计：** Phase2/3 设计 §4。

---

## File Structure

```
backend/app/
├── models/workflow.py            # Task 1（Workflow/Version/Execution/Todo/Template）
├── engine/
│   ├── __init__.py
│   ├── state.py                  # Task 2
│   ├── variable_resolver.py      # Task 2
│   ├── base.py                   # Task 3（BaseNodeExecutor + NodeRouter）
│   ├── nodes/                    # Task 3-7（12 执行器）
│   ├── graph_builder.py          # Task 8
│   └── executor.py               # Task 9（execute_workflow_task）
├── sse/bus.py                    # Task 10
├── api/v2/workflows.py           # Task 11
├── api/v2/executions.py          # Task 12
├── api/v2/todos.py               # Task 13
├── api/v2/templates.py           # Task 14
└── alembic/versions/0010_workflows.py
```

---

### Task 1: workflow ORM（5 表）+ 迁移

**Files:** `models/workflow.py` · migrate `0010_workflows.py` · `tests/test_wf_model.py`

- [ ] **Step 1: 实现 `models/workflow.py`**（字段对齐主方案 §4.3 + 前端 `types/workflow.ts`）

```python
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPk


class Workflow(Base, UUIDPk, TimestampMixin):
    __tablename__ = "workflows"
    user_id: Mapped = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")    # draft/published/archived
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    definition: Mapped | None = mapped_column(JSONB, nullable=True)     # {nodes, edges, global_variables}
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_run: Mapped | None = mapped_column(DateTime, nullable=True)
    webhook_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)


class WorkflowVersion(Base, UUIDPk, TimestampMixin):
    __tablename__ = "workflow_versions"
    workflow_id: Mapped = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    definition_snapshot: Mapped = mapped_column(JSONB)
    change_summary: Mapped | None = mapped_column(JSONB, nullable=True)


class WorkflowExecution(Base, UUIDPk, TimestampMixin):
    __tablename__ = "workflow_executions"
    workflow_id: Mapped = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    user_id: Mapped | None = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    trigger_type: Mapped[str] = mapped_column(String(20), default="manual")
    inputs: Mapped | None = mapped_column(JSONB, nullable=True)
    outputs: Mapped | None = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    node_progress: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped | None = mapped_column(DateTime, nullable=True)
    completed_at: Mapped | None = mapped_column(DateTime, nullable=True)


class WorkflowTodo(Base, UUIDPk, TimestampMixin):
    __tablename__ = "workflow_todos"
    execution_id: Mapped = mapped_column(ForeignKey("workflow_executions.id", ondelete="CASCADE"))
    workflow_id: Mapped = mapped_column(String(36))
    node_id: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_schema: Mapped | None = mapped_column(JSONB, nullable=True)
    form_data: Mapped | None = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/done/rejected/timeout
    deadline: Mapped | None = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped | None = mapped_column(DateTime, nullable=True)


class WorkflowTemplate(Base, UUIDPk, TimestampMixin):
    __tablename__ = "workflow_templates"
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="official")
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tags: Mapped = mapped_column(JSONB, default=list)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    node_count: Mapped[int] = mapped_column(Integer, default=0)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    definition: Mapped = mapped_column(JSONB)
```

- [ ] **Step 2: 注册 + 迁移 + 测试 + Commit** `feat(models): workflow 5 tables`

---

### Task 2: WorkflowState + VariableResolver

**Files:** `engine/state.py` · `engine/variable_resolver.py` · `tests/test_variable_resolver.py`

- [ ] **Step 1: 实现 `state.py`**

```python
from typing import TypedDict, Any, Optional
import uuid

def new_state(workflow_id, execution_id, user_id, inputs) -> dict:
    return {
        "workflow_id": workflow_id, "execution_id": execution_id,
        "thread_id": execution_id, "user_id": user_id,
        "variables": dict(inputs or {}), "node_outputs": {}, "current_node": None,
        "status": "running", "error": None, "node_timings": {},
        "debug_mode": False, "loop_stack": [],
    }
```

- [ ] **Step 2: 实现 `variable_resolver.py`**（解析 `{{node.output.x}}`/`{{workflow.custom.x}}`/`{{loop.item}}`）

```python
import re
_PAT = re.compile(r"\{\{\s*([\w.]+)(?:\[(\d+)\])?(\.\w+)?\s*\}\}")


def resolve(expr: str, state: dict) -> str:
    if not expr:
        return ""
    def _sub(m):
        path = m.group(1)
        if path.startswith("workflow.custom."):
            return str(state.get("variables", {}).get(path.split(".", 2)[-1], ""))
        if path.startswith("loop."):
            return str(state.get("_loop", {}).get(path.split(".", 1)[-1], ""))
        if "." in path:
            nid, field = path.split(".", 1)
            out = state.get("node_outputs", {}).get(nid, {})
            return str(out.get(field, ""))
        return m.group(0)
    return _PAT.sub(_sub, expr)
```

- [ ] **Step 3: 测试**（三类路径）+ Commit `feat(engine): state + variable resolver`

---

### Task 3: BaseNodeExecutor + NodeRouter + 基础节点

**Files:** `engine/base.py` · `engine/nodes/{start,end,variable_assign,template_render}.py` · `tests/test_base_nodes.py`

- [ ] **Step 1: 实现 `engine/base.py`**

```python
from abc import ABC, abstractmethod


class BaseNodeExecutor(ABC):
    type: str = "base"
    def __init__(self, node_def: dict):
        self.node_id = node_def["id"]
        self.config = node_def.get("data", {}).get("config", {})

    @abstractmethod
    async def run(self, state: dict) -> dict:
        """返回状态更新 dict（至少更新 node_outputs）"""


REGISTRY: dict[str, type[BaseNodeExecutor]] = {}


def register(cls):
    REGISTRY[cls.type] = cls
    return cls


def create(node_def: dict) -> BaseNodeExecutor:
    t = node_def.get("type")
    cls = REGISTRY.get(t)
    if not cls:
        raise ValueError(f"未知节点类型: {t}")
    return cls(node_def)
```

- [ ] **Step 2: 实现基础节点 `nodes/start.py` / `end.py` / `variable_assign.py` / `template_render.py`**

```python
# start.py
from app.engine.base import BaseNodeExecutor, register

@register
class StartNode(BaseNodeExecutor):
    type = "start"
    async def run(self, state):
        return {"node_outputs": {**state["node_outputs"], self.node_id: {"output": state["variables"]}}}

# end.py
@register
class EndNode(BaseNodeExecutor):
    type = "end"
    async def run(self, state):
        mapping = self.config.get("output_mapping", {})
        out = {k: state["variables"].get(v) for k, v in mapping.items()}
        return {"node_outputs": {**state["node_outputs"], self.node_id: {"output": out}}, "status": "completed"}

# variable_assign.py
@register
class VariableAssignNode(BaseNodeExecutor):
    type = "variable_assign"
    async def run(self, state):
        for a in self.config.get("assignments", []):
            tgt = a["target"].split(".")[-1]
            state["variables"][tgt] = a.get("value")
        return {"variables": state["variables"], "node_outputs": {**state["node_outputs"], self.node_id: {"output": state["variables"]}}}

# template_render.py
@register
class TemplateRenderNode(BaseNodeExecutor):
    type = "template_render"
    async def run(self, state):
        from jinja2 import Template
        tpl = Template(self.config.get("template", ""))
        rendered = tpl.render(**state["variables"])
        return {"node_outputs": {**state["node_outputs"], self.node_id: {"output": rendered}}}
```

- [ ] **Step 3: NodeRouter `engine/__init__.py` 触发所有节点注册**

```python
from app.engine.base import create, REGISTRY
from app.engine.nodes import start, end, variable_assign, template_render  # noqa
from app.engine.nodes import llm, rag, condition, loop, http, tool, code, human  # noqa（Task 4-7）
```

- [ ] **Step 4: 测试 + Commit** `feat(engine): base executor + basic nodes`

---

### Task 4: LLM 节点 + RAG 节点

**Files:** `engine/nodes/llm.py` · `engine/nodes/rag.py`

- [ ] **Step 1: LLM 节点**（复用 build_chat_model + LCEL）

```python
from app.engine.base import BaseNodeExecutor, register
from app.engine.variable_resolver import resolve
from app.providers.langchain_factory import build_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser

@register
class LLMNode(BaseNodeExecutor):
    type = "llm"
    async def run(self, state):
        import time; t0 = time.perf_counter()
        use = self.config.get("model", "qa")
        llm = await build_chat_model(use=use if use in ("qa","summary","rewrite") else "qa",
                                     temperature=self.config.get("temperature", 0.7),
                                     max_tokens=self.config.get("max_tokens"))
        prompt = ChatPromptTemplate.from_messages([
            ("system", resolve(self.config.get("system_prompt", ""), state)),
            ("human", resolve(self.config.get("user_prompt", "{question}"), state)),
        ])
        parser = JsonOutputParser() if self.config.get("output_mode") == "json" else StrOutputParser()
        out = await (prompt | llm | parser).ainvoke({})
        return {"node_outputs": {**state["node_outputs"], self.node_id: {"output": out}},
                "node_timings": {**state["node_timings"], self.node_id: (time.perf_counter()-t0)*1000}}
```

- [ ] **Step 2: RAG 节点**（复用 HybridRetriever，四端口）

```python
@register
class RAGNode(BaseNodeExecutor):
    type = "rag"
    async def run(self, state):
        from app.core.retrieval.hybrid_retriever import HybridRetriever
        from app.core.scenes import get_scene_config
        from app.core.reference_builder import build_references
        from app.providers.langchain_factory import build_chat_model
        query = resolve(self.config["query"], state)
        cfg = await get_scene_config(self.config.get("scene", "general"))
        r = HybridRetriever(doc_ids=self.config.get("document_ids", []), scene_config=cfg,
                            top_k=self.config.get("top_k", 5), enable_nav=self.config.get("enable_navigation", True))
        docs = await r.ainvoke(query)
        result = r.last_result
        citations = await build_references(result.chunks) if result else []
        answer = ""
        if self.config.get("generate_answer"):
            from app.core.generator.answer_chain import build_answer_chain, build_context
            llm = await build_chat_model(use="qa")
            answer = await build_answer_chain(llm).ainvoke({"system_prompt": cfg.system_prompt, "context": build_context(docs), "history": "", "question": query})
        return {"node_outputs": {**state["node_outputs"], self.node_id: {
            "chunks": [d.metadata for d in docs], "answer": answer, "citations": citations,
            "nav_anchors": result.nav_info["anchors"] if result and result.nav_info else []}}}
```

- [ ] **Step 3: Commit** `feat(engine): llm + rag nodes`

---

### Task 5: Condition + Loop 节点

**Files:** `engine/nodes/condition.py` · `engine/nodes/loop.py`

- [ ] **Step 1: Condition**（按 sourceHandle 路由）

```python
@register
class ConditionNode(BaseNodeExecutor):
    type = "condition"
    async def run(self, state):
        for rule in self.config.get("conditions", []):
            if self._eval(rule, state):
                return {"_branch": rule["id"]}
        return {"_branch": self.config.get("default_branch", "else")}
    def _eval(self, rule, state):
        # 简化：评估 expression（实际可用 simpleeval 库）
        from app.engine.variable_resolver import resolve
        try:
            expr = resolve(rule.get("expression", ""), state)
            return bool(eval(expr))      # 注意：生产用沙箱表达式引擎
        except Exception:
            return False
```

- [ ] **Step 2: Loop**（for_each/while，max_iterations 安全阀）

```python
@register
class LoopNode(BaseNodeExecutor):
    type = "loop"
    async def run(self, state):
        # 简化：记录循环上下文；实际由 graph 结构驱动 body/done 分支
        return {"node_outputs": {**state["node_outputs"], self.node_id: {"output": "loop"}}}
```

- [ ] **Step 3: Commit** `feat(engine): condition + loop nodes`

---

### Task 6: HTTP + Tool 节点

**Files:** `engine/nodes/http.py` · `engine/nodes/tool.py`

- [ ] **Step 1: HTTP**（httpx + 变量插值）

```python
@register
class HTTPNode(BaseNodeExecutor):
    type = "http"
    async def run(self, state):
        import httpx, time
        from app.engine.variable_resolver import resolve
        t0 = time.perf_counter()
        cfg = self.config
        async with httpx.AsyncClient(timeout=cfg.get("timeout_seconds", 30)) as c:
            resp = await c.request(cfg.get("method", "GET"), resolve(cfg["url"], state),
                                   headers=cfg.get("headers", {}), json=cfg.get("body"))
        data = resp.json() if resp.headers.get("content-type","").startswith("application/json") else resp.text
        return {"node_outputs": {**state["node_outputs"], self.node_id: {"output": data, "status": resp.status_code}}}
```

- [ ] **Step 2: Tool**（复用 Plan 8 的 tool executor，此处先占位调用）

```python
@register
class ToolNode(BaseNodeExecutor):
    type = "tool"
    async def run(self, state):
        from app.services.tool_service import execute_tool
        from app.engine.variable_resolver import resolve
        params = {k: resolve(v, state) for k, v in self.config.get("parameters", {}).items()}
        result = await execute_tool(self.config["tool_id"], params)
        return {"node_outputs": {**state["node_outputs"], self.node_id: {"output": result}}}
```

> `execute_tool` 在 Plan 8 实现；此处先建 `tool_service.execute_tool` 占位（返回 params），Plan 8 替换。

- [ ] **Step 3: Commit** `feat(engine): http + tool nodes`

---

### Task 7: Code 节点（沙箱）+ Human 节点（人工介入）

**Files:** `engine/nodes/code.py` · `engine/nodes/human.py`

- [ ] **Step 1: Code**（引用 Docker 沙箱，Phase2 沙箱池）

```python
@register
class CodeNode(BaseNodeExecutor):
    type = "code"
    async def run(self, state):
        from app.engine.variable_resolver import resolve
        from app.providers.sandbox import run_in_sandbox   # Docker 沙箱池（本 plan Task 15 实现）
        inputs = {k: resolve(v, state) for k, v in self.config.get("input_mapping", {}).items()}
        r = await run_in_sandbox(code=self.config["code"], inputs=inputs,
                                 timeout=self.config.get("timeout_seconds", 30),
                                 memory_mb=self.config.get("memory_limit_mb", 256))
        return {"node_outputs": {**state["node_outputs"], self.node_id: {"output": r.output, "logs": r.logs}}}
```

- [ ] **Step 2: Human**（创建 todo，interrupt）

```python
@register
class HumanNode(BaseNodeExecutor):
    type = "human"
    async def run(self, state):
        from app.services.todo_service import create_todo_for_human
        await create_todo_for_human(execution_id=state["execution_id"], node_id=self.node_id,
                                    title=self.config.get("title", "待审核"),
                                    form_schema=self.config.get("form_schema", []),
                                    timeout_hours=self.config.get("timeout_hours", 24))
        return {"current_node": self.node_id}   # interrupt_before 已暂停
```

- [ ] **Step 3: Commit** `feat(engine): code(sandbox) + human nodes`

---

### Task 8: GraphBuilder + checkpoint（AsyncPostgresSaver）

**Files:** `engine/graph_builder.py` · `tests/test_graph_builder.py`

- [ ] **Step 1: 实现**

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.engine import create as create_node   # 触发注册
from app.config import settings


class GraphBuilder:
    async def build(self, definition: dict, debug: bool = False):
        nodes = definition["nodes"]; edges = definition.get("edges", [])
        graph = StateGraph(dict)
        for nd in nodes:
            executor = create_node(nd)
            graph.add_node(nd["id"], executor.run)
        for e in edges:
            src, tgt = e["source"], e["target"]
            handle = e.get("sourceHandle")
            if handle and handle not in ("output", None):
                graph.add_conditional_edges(src, lambda st, h=handle: st.get("_branch") or h, {handle: tgt})
            else:
                graph.add_edge(src, tgt)
        start_id = next(n["id"] for n in nodes if n["type"] == "start")
        graph.add_edge(START, start_id)
        for n in nodes:
            if n["type"] == "end":
                graph.add_edge(n["id"], END)
        checkpointer = AsyncPostgresSaver.from_conn_string(settings.database_url)
        await checkpointer.setup()
        interrupt = ["*"] if debug else [n["id"] for n in nodes if n["type"] == "human"]
        return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt)
```

- [ ] **Step 2: 测试**（start→llm(mock)→end 编译+跑通）+ Commit `feat(engine): graph builder + postgres checkpoint`

---

### Task 9: execute_workflow_task（ARQ + astream + 进度）

**Files:** `engine/executor.py` · 修改 `worker/app.py`（注册任务）· `tests/test_executor.py`

- [ ] **Step 1: 实现 `executor.py`**

```python
import time
from sqlalchemy import select, update
from app.db.session import async_session
from app.models.workflow import WorkflowExecution, Workflow, WorkflowVersion
from app.engine.state import new_state
from app.engine.graph_builder import GraphBuilder
from app.sse.bus import SSEBus


async def _set_status(eid, status, **kw):
    async with async_session() as s:
        await s.execute(update(WorkflowExecution).where(WorkflowExecution.id == eid).values(status=status, **kw))
        await s.commit()


async def _load_definition(workflow_id, version):
    async with async_session() as s:
        if version:
            v = (await s.execute(select(WorkflowVersion).where(WorkflowVersion.workflow_id == workflow_id, WorkflowVersion.version == version))).scalar_one_or_none()
            return v.definition_snapshot
        wf = (await s.execute(select(Workflow).where(Workflow.id == workflow_id))).scalar_one()
        return wf.definition


async def execute_workflow(ctx, execution_id: str):
    async with async_session() as s:
        ex = (await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == execution_id))).scalar_one()
        eid, wid, ver, uid = str(ex.id), str(ex.workflow_id), ex.version, ex.user_id
    definition = await _load_definition(wid, ver)
    graph = await GraphBuilder().build(definition, debug=False)
    config = {"configurable": {"thread_id": eid}}
    initial = new_state(wid, eid, uid, {})
    await _set_status(eid, "running", started_at=time.utcnow())
    await SSEBus.publish(f"exec:{eid}", {"event": "execution_start", "total_nodes": len(definition["nodes"])})
    try:
        async for ev in graph.astream(initial, config=config, stream_mode="updates"):
            for nid, upd in ev.items():
                if nid in (START, END): continue
                await SSEBus.publish(f"exec:{eid}", {"event": "node_complete", "node_id": nid, "output_summary": str(upd)[:200]})
        async with async_session() as s:
            await s.execute(update(WorkflowExecution).where(WorkflowExecution.id == eid).values(status="completed", completed_at=time.utcnow()))
            await s.commit()
        await SSEBus.publish(f"exec:{eid}", {"event": "execution_complete", "success": True})
    except Exception as e:
        await _set_status(eid, "failed", error=str(e), completed_at=time.utcnow())
        await SSEBus.publish(f"exec:{eid}", {"event": "execution_error", "error": str(e)})
```

- [ ] **Step 2: 注册到 `worker/app.py`** `functions = [parse_document_task, execute_workflow]`（import `from app.engine.executor import execute_workflow`）

- [ ] **Step 3: Commit** `feat(engine): execute_workflow arq task`

---

### Task 10: SSEBus + execution stream API

**Files:** `app/sse/bus.py` · `app/api/v2/executions.py` · `tests/test_sse_bus.py`

- [ ] **Step 1: 实现 `sse/bus.py`**

```python
import json, asyncio
from app.db.redis import get_redis


class SSEBus:
    @staticmethod
    async def publish(channel: str, event: dict):
        r = await get_redis()
        await r.publish(channel, json.dumps(event, ensure_ascii=False))

    @staticmethod
    async def subscribe(channel: str):
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    yield json.loads(msg["data"])
        finally:
            await pubsub.unsubscribe(channel)
```

- [ ] **Step 2: 实现 `api/v2/executions.py`（stream + list + cancel/resume/debug）**

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.workflow import WorkflowExecution
from app.sse.bus import SSEBus
import json

router = APIRouter(tags=["executions"])


@router.get("/executions")
async def list_(workflowId: str | None = None, limit: int = 20, me=Depends(get_current_user)):
    async with async_session() as s:
        q = select(WorkflowExecution).order_by(WorkflowExecution.created_at.desc()).limit(limit)
        if workflowId: q = q.where(WorkflowExecution.workflow_id == workflowId)
        rows = (await s.execute(q)).scalars().all()
    return ok([{"id": str(r.id), "workflowId": str(r.workflow_id), "status": r.status,
                "trigger": r.trigger_type, "startTime": r.started_at.isoformat() if r.started_at else "",
                "duration": r.duration_ms, "nodeProgress": r.node_progress or ""} for r in rows])


@router.get("/executions/{eid}/stream")
async def stream(eid: str, me=Depends(get_current_user)):
    async def gen():
        async for ev in SSEBus.subscribe(f"exec:{eid}"):
            yield f"event: {ev['event']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/executions/{eid}/cancel")
async def cancel(eid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        await s.execute(update_stmt_status(eid, "cancelled"))  # 简化：标记 cancelled
        await s.commit()
    await SSEBus.publish(f"exec:{eid}", {"event": "execution_error", "error": "cancelled"})
    return ok({"success": True})
```

> 简化：cancel 仅标记状态 + 推事件；真正中断 worker 需共享取消标志（Redis key），后续增强。

- [ ] **Step 3: 挂载 + 测试 + Commit** `feat(execution): sse bus + /stream + list + cancel`

---

### Task 11: workflow API（CRUD/publish/duplicate/execute）

**Files:** `app/api/v2/workflows.py` · `app/schemas/workflow.py` · `main.py`

- [ ] **Step 1: 实现 CRUD + publish + duplicate + execute**

```python
from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel
from sqlalchemy import select, update, func
from arq import create_pool
from arq.connections import RedisSettings
from app.api.deps import get_current_user
from app.api.response import ok
from app.config import settings
from app.db.session import async_session
from app.models.workflow import Workflow, WorkflowVersion, WorkflowExecution
from app.exceptions import BizException, ErrorCode

router = APIRouter(prefix="/workflows", tags=["workflows"])

class WfCreate(BaseModel):
    name: str
    description: str | None = None

@router.get("")
async def list_(me=Depends(get_current_user)):
    async with async_session() as s:
        rows = (await s.execute(select(Workflow).order_by(Workflow.created_at.desc()))).scalars().all()
    return ok([_out(r) for r in rows])

@router.post("")
async def create(body: WfCreate, me=Depends(get_current_user)):
    async with async_session() as s:
        wf = Workflow(user_id=str(me.id), name=body.name, description=body.description, definition={"nodes":[], "edges":[]})
        s.add(wf); await s.commit(); await s.refresh(wf)
    return ok(_out(wf))

@router.get("/{wid}")
async def detail(wid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one_or_none()
    return ok(_out(wf, with_def=True))

@router.put("/{wid}")
async def update_(wid: str, body: dict = Body(...), me=Depends(get_current_user)):
    async with async_session() as s:
        await s.execute(update(Workflow).where(Workflow.id == wid).values(name=body.get("name"), description=body.get("description"), definition=body.get("definition", {})))
        await s.commit()
    return ok({"success": True})

@router.delete("/{wid}")
async def delete_(wid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        await s.execute(delete(Workflow).where(Workflow.id == wid)); await s.commit()
    return ok({"success": True})

@router.post("/{wid}/publish")
async def publish(wid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one()
        ver = wf.current_version + 1
        s.add(WorkflowVersion(workflow_id=wid, version=ver, definition_snapshot=wf.definition))
        await s.execute(update(Workflow).where(Workflow.id == wid).values(status="published", current_version=ver))
        await s.commit()
    return ok({"version": ver})

@router.post("/{wid}/duplicate")
async def duplicate(wid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        orig = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one()
        nw = Workflow(user_id=str(me.id), name=orig.name + " (副本)", definition=orig.definition)
        s.add(nw); await s.commit(); await s.refresh(nw)
    return ok(_out(nw))

@router.post("/{wid}/execute")
async def execute(wid: str, body: dict = Body(default={}), me=Depends(get_current_user)):
    async with async_session() as s:
        wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one()
        if wf.status != "published": raise BizException(ErrorCode.PARAM_ERROR, "workflow 未发布")
        ex = WorkflowExecution(workflow_id=wid, version=wf.current_version, user_id=str(me.id), trigger_type="manual", inputs=body.get("inputs", {}))
        s.add(ex); await s.commit(); await s.refresh(ex)
        eid = str(ex.id)
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job("execute_workflow", eid)
    return ok({"executionId": eid})

def _out(wf, with_def=False):
    d = {"id": str(wf.id), "name": wf.name, "description": wf.description, "status": wf.status,
         "version": wf.current_version, "icon": wf.icon, "createdAt": wf.created_at.isoformat() if wf.created_at else ""}
    if with_def: d["definition"] = wf.definition
    return d
```

- [ ] **Step 2: 挂载 + Commit** `feat(workflow): CRUD + publish + duplicate + execute`

---

### Task 12: 调试 API（debug/continue, test-node, resume）

**Files:** 追加到 `api/v2/executions.py` · `tests/test_debug_api.py`

- [ ] **Step 1: 实现**

```python
@router.post("/executions/{eid}/resume")
async def resume(eid: str, me=Depends(get_current_user)):
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job("execute_workflow", eid)   # 简化：从 checkpoint 恢复需 astream(None)
    return ok({"success": True})

@router.post("/executions/{eid}/debug/continue")
async def debug_continue(eid: str, me=Depends(get_current_user)):
    # 单步：graph.astream(None, config) 推进一步（需重建 graph 并复用 thread_id checkpoint）
    return ok({"success": True})

class TestNodeBody(BaseModel):
    nodeId: str
    mockInputs: dict = {}

@router.post("/executions/{eid}/debug/test-node")
async def test_node(eid: str, body: TestNodeBody, me=Depends(get_current_user)):
    from app.engine import create as create_node
    from app.models.workflow import WorkflowExecution
    async with async_session() as s:
        ex = (await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))).scalar_one()
        wf = (await s.execute(select(Workflow).where(Workflow.id == ex.workflow_id))).scalar_one()
    nd = next(n for n in wf.definition["nodes"] if n["id"] == body.nodeId)
    executor = create_node(nd)
    mock_state = {"variables": body.mockInputs, "node_outputs": {}, "execution_id": eid}
    result = await executor.run(mock_state)
    return ok({"nodeId": body.nodeId, "success": True, "outputs": result.get("node_outputs", {}).get(body.nodeId)})

@router.get("/executions/{eid}/nodes/{node_id}")
async def node_detail(eid: str, node_id: str, me=Depends(get_current_user)):
    return ok({"nodeId": node_id, "detail": "（节点详情从 checkpoint/state 读取，简化）"})
```

- [ ] **Step 2: Commit** `feat(workflow): debug continue + test-node + resume`

---

### Task 13: todos API（人工介入）

**Files:** `app/services/todo_service.py` · `app/api/v2/todos.py` · `main.py`

- [ ] **Step 1: 实现 `todo_service.py`**

```python
from sqlalchemy import select, update
from app.db.session import async_session
from app.models.workflow import WorkflowTodo
from datetime import datetime, timedelta


async def create_todo_for_human(execution_id, node_id, title, form_schema, timeout_hours, workflow_id=None):
    async with async_session() as s:
        t = WorkflowTodo(execution_id=execution_id, workflow_id=workflow_id, node_id=node_id,
                         title=title, form_schema=form_schema, status="pending",
                         deadline=datetime.utcnow() + timedelta(hours=timeout_hours))
        s.add(t); await s.commit(); await s.refresh(t)
        return t


async def list_todos(status: str | None, user):
    async with async_session() as s:
        q = select(WorkflowTodo).order_by(WorkflowTodo.created_at.desc())
        if status == "pending": q = q.where(WorkflowTodo.status == "pending")
        elif status == "done": q = q.where(WorkflowTodo.status.in_(["done", "rejected"]))
        rows = (await s.execute(q)).scalars().all()
    return rows


async def submit(todo_id, form_data):
    async with async_session() as s:
        await s.execute(update(WorkflowTodo).where(WorkflowTodo.id == todo_id).values(status="done", form_data=form_data, submitted_at=datetime.utcnow()))
        await s.commit()
    # resume 对应 execution（从 checkpoint）
    from app.services.resume import resume_execution
    todo = await _get(todo_id)
    await resume_execution(str(todo.execution_id), form_data)


async def reject(todo_id):
    async with async_session() as s:
        await s.execute(update(WorkflowTodo).where(WorkflowTodo.id == todo_id).values(status="rejected"))
        await s.commit()
```

- [ ] **Step 2: 实现 `api/v2/todos.py`**

```python
router = APIRouter(tags=["todos"])

@router.get("/todos")
async def list_(status: str | None = None, me=Depends(get_current_user)):
    rows = await todo_service.list_todos(status, me)
    return ok([{"id": str(t.id), "title": t.title, "source": t.source, "status": t.status,
                "submittedAt": t.submitted_at.isoformat() if t.submitted_at else None,
                "deadline": int((t.deadline - datetime.utcnow()).total_seconds()) if t.deadline else None,
                "formSchema": t.form_schema, "formData": t.form_data} for t in rows])

@router.get("/todos/{tid}")
async def detail(tid: str, me=Depends(get_current_user)):
    return ok(await todo_service.get(tid))

@router.post("/todos/{tid}/submit")
async def submit_(tid: str, body: dict = Body(...), me=Depends(get_current_user)):
    await todo_service.submit(tid, body.get("form_data", {}))
    return ok({"todo_id": tid, "status": "done"})

@router.post("/todos/{tid}/reject")
async def reject_(tid: str, me=Depends(get_current_user)):
    await todo_service.reject(tid)
    return ok({"todo_id": tid, "status": "rejected"})
```

- [ ] **Step 3: 挂载 + Commit** `feat(workflow): todos (human intervention) api`

---

### Task 14: templates API

**Files:** `app/api/v2/templates.py` · `main.py`

- [ ] **Step 1: 实现**

```python
router = APIRouter(prefix="/templates", tags=["templates"])

@router.get("")
async def list_(me=Depends(get_current_user)):
    async with async_session() as s:
        rows = (await s.execute(select(WorkflowTemplate).order_by(WorkflowTemplate.use_count.desc()))).scalars().all()
    return ok([{"id": str(r.id), "name": r.name, "description": r.description, "source": r.source,
                "tags": r.tags, "nodeCount": r.node_count, "useCount": r.use_count} for r in rows])

@router.post("/{tid}/instantiate")
async def instantiate(tid: str, body: dict = Body(default={}), me=Depends(get_current_user)):
    async with async_session() as s:
        tpl = (await s.execute(select(WorkflowTemplate).where(WorkflowTemplate.id == tid))).scalar_one()
        wf = Workflow(user_id=str(me.id), name=body.get("name") or tpl.name, description=tpl.description, definition=tpl.definition)
        s.add(wf); await s.commit(); await s.refresh(wf)
    return ok({"id": str(wf.id)})
```

- [ ] **Step 2: Commit** `feat(workflow): templates api`

---

### Task 15: Code 沙箱（Docker 容器池）+ 冒烟

**Files:** `app/providers/sandbox.py` · 依赖 `docker` 包 · `tests/test_sandbox.py`

- [ ] **Step 1: 加依赖** `pyproject.toml` 追加 `"docker>=7.0"`

- [ ] **Step 2: 实现 `sandbox.py`**

```python
import asyncio, json, time
from dataclasses import dataclass

@dataclass
class SandboxResult:
    ok: bool
    output: object
    error: str | None
    logs: list[str]
    duration: int


_IMAGE = "python:3.11-slim"


async def run_in_sandbox(code: str, inputs: dict, timeout: int = 30, memory_mb: int = 256, network: bool = False) -> SandboxResult:
    """在 Docker 容器中执行 Python 代码。inputs 经 stdin 传入，result 经 stdout 返回。"""
    import docker
    t0 = time.perf_counter()
    wrapper = (
        "import json, sys, io\n"
        f"inputs = json.loads(sys.stdin.read())\n"
        "try:\n"
        f"    exec({code!r})\n"
        "    sys.stdout.write(json.dumps({'result': result if 'result' in dir() else None}))\n"
        "except Exception as e:\n"
        "    sys.stdout.write(json.dumps({'error': str(e)}))\n"
    )

    def _run():
        client = docker.from_env()
        out = client.containers.run(_IMAGE, ["python", "-c", wrapper],
                                    input=json.dumps(inputs).encode(), mem_limit=f"{memory_mb}m",
                                    network_mode="none" if not network else "bridge",
                                    detach=False, stdout=True, stderr=True)
        return out

    try:
        raw = await asyncio.to_thread(_run)
        text = raw.decode() if isinstance(raw, bytes) else str(raw)
        data = json.loads(text.split("}{")[0] + "}" if text.count("{") > 1 else text) if text.strip() else {}
        return SandboxResult(ok="error" not in data, output=data.get("result"), error=data.get("error"),
                             logs=[], duration=int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        return SandboxResult(ok=False, output=None, error=str(e), logs=[], duration=int((time.perf_counter() - t0) * 1000))
```

- [ ] **Step 3: 测试**（简单 print 代码）+ Commit `feat(sandbox): docker code execution pool`

- [ ] **Step 4: 端到端冒烟**

```bash
# 发布一个最小 workflow（start→llm→end），执行，看 SSE
curl -N http://localhost:8000/api/v2/executions/<eid>/stream -H "Authorization: Bearer $TOKEN"
```
Expected: 流式 execution_start → node_complete → execution_complete。

- [ ] **Step 5: Commit** `test: phase2 workflow e2e smoke`

---

## Plan 7 完成标志
- ✅ 5 张工作流表 + 迁移
- ✅ GraphBuilder（definition → StateGraph，条件边）+ AsyncPostgresSaver checkpoint
- ✅ 12 节点执行器（start/end/llm/rag/code/http/condition/loop/human/tool/variable_assign/template_render）
- ✅ execute_workflow（ARQ + astream + SSE 进度）
- ✅ workflow API（CRUD/publish/duplicate/execute）+ execution SSE + 调试（continue/test-node/resume/cancel）
- ✅ todos（人工介入 submit/reject）+ templates + Docker 代码沙箱

**下一步：** Plan 8 tools/skills/mcp。

*— 计划结束 —*

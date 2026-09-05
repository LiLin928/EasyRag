# EasyRag 后端代码全景说明（v0.1）

> 适用代码：`D:/4-MyProject/EasyRag/backend/app/**`
> 生成日期：2026-09-04
> 范围：FastAPI 应用骨架、文档处理、工作流执行、智能体执行、横向能力。

---

## 一、应用骨架与总览

`app/main.py` 用 FastAPI 启动，注册 27 个 `app/api/v2/*.py` 路由、CORS 中间件、限流（`slowapi`）、请求 id 中间件（写入 `X-Request-ID` 并绑定 structlog contextvars）、`BizException` 全局异常处理器（统一返回 `{code,message,data}` 三段式）。

- `lifespan` 启动钩子：`ensure_admin()` → `run_seed()` → `configure_tracing()`（langsmith / langfuse / none 三选一）。
- 队列与可观测性：原来的 `arq/redis` 已被替换为「PostgreSQL 队列 + PostgreSQL 事件总线」（`app/core/engine/pg_queue.py`、`sse_bus_pg.py`），降低了对 Redis 的依赖。
- 数据层：`SQLAlchemy 2.0 async + Alembic`，单例 `async_session()`；模型在 `app/models/`（document / chunk / knowledge_base / workflow / agent / tool / skill / mcp / metadata / audit 等）。

---

## 二、文档处理（Upload → Parse → Chunk → Embed）

### 1) 入口 API（`app/api/v2/assets.py` → `documents.upload`）

- 校验：扩展名白名单 `{pdf, docx, doc, xlsx, xls, md, txt, markdown}`、≤50 MB、所属 KB 归属当前用户。
- 落库：写 `Document`（status=pending）+ `ParseTask`，拼 `file_key = "{kb_id}/{doc_id}/{filename}"`。
- 存对象：通过 `get_storage()`（`app/providers/storage/factory.py`）落到 **Local FS 或 MinIO**（由 `settings.storage_type` 决定）。
- 入队：`PGJobQueue.enqueue_task('parse_document', {"doc_id": ...})` —— 不阻塞 HTTP，立即返回 `{task_id, doc_id}`。
- 前端轮询 `GET /parse-tasks/{task_id}`（`parse_tasks.py`）拿到 `{status, pct, error}` 推进度条。

### 2) Worker 侧执行（`app/worker/pg_worker.py` → `_execute_parse_document`）

Worker 是一个常驻进程（`pg_worker_main.py` 启动入口），用 `SELECT … FOR UPDATE SKIP LOCKED` 从 `job_queue` 取任务，解析成功后调用 `publish(execution_id, event, data)` 把事件写入 `execution_events` 表，由 SSE 订阅者读出。

> ⚠️ 当前实现里 `_execute_parse_document` 仍是占位实现；规划路径如下：

### 3) 规划中的解析流水线（`app/core/parser/`）

| 文件 | 行为 |
|---|---|
| `dispatcher.py::parse(ext, path)` | 按扩展名分发到对应解析器 |
| `pdf_parser.py` | `pymupdf (fitz)` 抽取文本块 + `pdfplumber` 抽表格转 HTML |
| `docx_parser.py` | `python-docx`，Heading N → heading + level，title → heading lvl=1 |
| `md_parser.py` | 正则 `^(#{1,6})\s+…` 判 heading，其余为 text |
| `xlsx_parser.py` | `openpyxl`，每个 sheet → 一个 table HTML，`section_path = sheet 名` |
| `mineru.py` | 远程 HTTP 服务 `POST {mineru_url}/parse`，返回 `ParsedDocument {sections, tables, images}` |
| `tree_builder.py::build_tree(doc_id, elements)` | 把 heading 元素按层级入栈 →写 `tree_nodes` 表，根节点=文档，其余 `parent_id` 指向更浅层 heading |
| `chunker.py::chunk(elements, chunk_size=512, overlap=64)` | 按 heading 分节、节内滑窗切分；输出字段 `content / content_search / page_number / section_path / clause_title / seq` |
| `models.py::ParsedElement` | dataclass：`element_type ∈ {text,table,image,heading}, content, page_number, section_path, image_key, level` |

**完整链路**：

```
upload → DB(Document/ParseTask pending) → storage.put()
 → PGJobQueue.enqueue_task('parse_document')
      → PGWorker 拉取
 → parser.dispatch(ext) # → list[ParsedElement]
      → tree_builder.build_tree()  # → 写 tree_nodes
      → chunker.chunk()            # → list[chunk dict]
      → (规划中) embed &写 chunks + embeddings
      → ParseTask.status='success', doc.element_count/chunk_count 回填
      → publish('task_complete') # SSE 推前端
```

资产元数据走 `app/services/asset_service.py`：所有权校验（join KnowledgeBase 验 user_id）、KB metadata 字段 schema 校验、按 `metadata_*` 列精确/范围筛选、分页与多字段排序、批量启用/禁用、元数据批量更新。模型层 `KbMetadataField.scope ∈ {document, chunk}`，mapped 字段（document_name/file_size/uploader/…）不允许自定义编辑。

---

## 三、工作流执行（Definition → LangGraph → SSE）

### 1) 工作流定义与版本

- 模型：`app/models/workflow.py` 中 `Workflow / WorkflowVersion / WorkflowExecution / WorkflowTodo`。
- 存储：`Workflow.definition` JSONB = `{nodes, edges}`；发布则把当前定义快照写到 `WorkflowVersion.definition_snapshot`，`current_version` 自增。

### 2) 编辑 API（`app/api/v2/workflows.py`）

`GET/POST/PUT/DELETE /workflows`、`POST /{wid}/publish`、`POST /{wid}/duplicate`、`POST /{wid}/execute`、`POST /{wid}/versions/{v}/rollback`。

### 3) 触发执行（`POST /workflows/{wid}/execute`）

调 `app/core/engine.arq_client.enqueue_workflow_task(workflow_id, inputs, trigger, user_id)`：

1. 读取 workflow + version 获取 definition；
2. 调 `PGJobQueue.enqueue(...)` 创建 `WorkflowExecution` 行 + `job_queue` 行，返回 `execution_id`。

HTTP 立刻返回 `{execution_id}`，前端拿到后订阅 SSE。

### 4) 编译（`app/core/engine/graph_builder.py::GraphBuilder.build`）

把前端拖出来的 JSON 编译成 LangGraph：

1. 遍历 `nodes`，按 `type` 调 `NodeRouter.create(node_def)` 拿到 `BaseNodeExecutor`，`graph.add_node(id, executor.run)`。
2. 遍历 `edges`：带 `sourceHandle` 的（条件分支）走 `add_conditional_edges`；普通边走 `add_edge`。
3. `START → start 节点`、`end 节点 → END`。
4. `checkpointer = await get_checkpointer()`：dev=MemorySaver，prod=AsyncPostgresSaver（`app/core/agent/memory.py`）。
5. `interrupt_before`：debug 模式 = `["*"]`（所有节点前暂停）；否则 = 所有 human 节点 id。
6. `graph.compile(checkpointer=..., interrupt_before=...)` 得到 CompiledStateGraph。

### 5) Worker 执行（`_execute_workflow`）

1. 从 DB 读 `WorkflowExecution`、`Workflow`、`WorkflowVersion`，拿到 definition。
2. `graph = await GraphBuilder().build(definition, execution_id, debug=...)`。
3. 用 LangGraph `stream(..., config={"configurable": {"thread_id": exec_id}})` 跑。
4. 每跳节点后 `publish(exec_id, "node_complete", {node_id, output, timing})`。
5. 结束：`publish("execution_complete", {status, duration_ms})` + `executor.status = 'completed' / 'failed' / 'cancelled' / 'paused'`，并写 `duration_ms`。
6. 中断点：debug 模式在每个节点前抛 GraphInterrupt；human 节点把 `WorkflowTodo` 落库（deadline/timeout_hours）并把执行置 `paused`，等 `POST /executions/{eid}/resume`（调 `PGJobQueue._requeue_paused`）恢复。

### 6) 12 种内置节点（`app/core/engine/nodes/basic.py`，注册到 `NodeRouter`）

| type | 类 | 关键逻辑 |
|---|---|---|
| `start` / `end` | `StartExecutor` / `EndExecutor` | 仅设置 `current_node`；end 设 `status="completed"` |
| `llm` | `LLMExecutor` | `build_chat_model("qa")` + `ChatPromptTemplate(system, user)` → StrOutputParser；记录 `node_timings` |
| `rag` | `RAGExecutor` | `get_scene_config("general")` → `HybridRetriever(doc_ids, scene, top_k, enable_nav)`；可选 `generate_answer=true` 再调一次 LLM；输出 `{chunks, answer}` |
| `http` | `HTTPExecutor` | `httpx.AsyncClient`；支持 method/url/body/headers/timeout |
| `tool` | `ToolExecutor` | `ToolService.execute_tool` 调挂载的 Tool（HTTP/Python/DB） |
| `condition` | `ConditionExecutor` | 解析 `{{var}}` 求值，支持 `==/!=/contains/>/<`；返回 handle 字符串决定边 |
| `loop` | `LoopExecutor` | 从 items 节点拉列表，按 `loop_stack` 推进；把 `{item, index}` 写到 `_loop`，items 用完时清栈触发跳出 |
| `human` | `HumanExecutor` | 写 `WorkflowTodo`，置 execution `paused` |
| `code` | `CodeExecutor` | 优先 `app.providers.sandbox.run_in_sandbox`；fallback 到本地 `exec(code, {__builtins__, args}, local)` 暴露 `result` |
| `variable_assign` | `VariableAssignExecutor` | 遍历 `assignments[]`，把 `{{...}}` 表达式结果写入 `state.variables` |
| `template_render` | `TemplateRenderExecutor` | Jinja2 渲染；失败回退到简单插值 |

### 7) 状态与插值（`app/core/engine/state.py`）

- `WorkflowState(TypedDict)`：workflow_id / execution_id / thread_id / user_id / **variables**（`workflow.custom.*`） / **node_outputs**（`{{node_id.output.field}}`） / current_node / status / error / started_at / **node_timings** / debug_mode / loop_stack。
- `resolve(expr, state)` 与 `resolve_dict(d, state)` 递归解析 `{{…}}`：支持 `{{workflow.custom.x}}`、`{{node_id.output[0].field}}`、`{{loop.item}}`。
- PGJobQueue 用 `SELECT … FOR UPDATE SKIP LOCKED` + `priority DESC, created_at ASC` 抢任务；提供 `enqueue / dequeue / complete / cancel / is_cancelled / _requeue_paused / enqueue_task(generic)`。

### 8) 调试端点（`app/api/v2/executions.py`）

- `POST /{eid}/resume`：把 paused 任务重排回 pending。
- `POST /{eid}/debug/continue`：单步续跑。
- `POST /{eid}/debug/test-node`：拿当前 execution 的 `state` 直接 `executor.run(state)`，不落库（用于编辑器里点一下试一下）。
- `GET /{eid}/nodes/{node_id}`：查节点元数据。
- `GET /{eid}/stream`：**SSE 事件流** —— 先回放 `execution_events` 表历史，再 0.5s 轮询新行；遇 `execution_complete/error/cancelled/paused` 自动关闭。

---

## 四、智能体执行（ReAct Agent + 五类工具挂载）

### 1) Agent 模型（`app/models/agent.py`）

```python
Agent(name, description, model, prompt, temp, maxtok,
      tools=[ToolID], docs=[DocID], wfs=[WorkflowID],
      mcps=[McpID], skills=[SkillID], enabled)
```

**五类挂载资源** 统一由 Agent 持有；运行时统一转成 LangChain `BaseTool` 列表。

### 2) 工具聚合（`app/core/agent/tool_registry.py::build_tools`）

按顺序聚合：

| 来源 | 转换 | 行为 |
|---|---|---|
| `tools`（HTTP/Python/DB 工具） | `Tool` → `StructuredTool`，`args_schema` 用 pydantic `create_model` 动态生成；运行时调 `tool_service.execute_tool` | |
| `docs` | `search_documents` `@tool`，复用 `HybridRetriever(doc_ids, scene="general", top_k=5, enable_nav=False)` | 在挂载文档中检索 |
| `wfs` | `workflow_<name>` `StructuredTool`，调 `enqueue_workflow_task(...)`，**同步轮询** PGJobQueue（≤60s）拿 `outputs` 后返回 JSON | |
| `mcps`（`tool_adapters/mcp_tools.py::load_tools`） | 用 `langchain-mcp-adapters` 把 MCP server 暴露的工具直接 `extend(tools)` | |
| `skills` | `StructuredTool(name=sk.name)`，调用返回 `[SKILL name]\n{sk.prompt}` 前缀字符串，由 LLM 自行取用 | |

### 3) 对话执行（`app/services/agent_service.py::AgentService.chat`）

```python
llm   = build_chat_model(use="qa", temperature=agent.temp)
tools = await build_tools(agent)
agent = create_react_agent(model=llm, tools=tools,
                           state_modifier=agent.prompt or "",
                           checkpointer=await get_checkpointer())
```

- **thread_id = `agent:{aid}:{user_id}`** ，复用 LangGraph 持久化层做多轮记忆。
- 用 `agent.astream_events({messages:[("user", question)]}, version="v2")` 流式输出，对齐前端 `types/agent.ts` 事件协议：

| LangGraph event | SSE 事件 |
|---|---|
| — 开始 | `phase {phase:"generate"}` |
| `on_tool_start` | `tool_start {tool, input}` |
| `on_tool_end` | `tool_end {tool, output}` |
| `on_chat_model_stream` | `token {token}` |
| 结束 | `done {agentId}`，更新 `agent.last_active = now` |
| 异常 | `error {code, message}` |

### 4) HTTP 入口（`app/api/v2/agents.py::POST /{aid}/chat`）

返回 `StreamingResponse(media_type="text/event-stream")`，中间包一层 try/except 把任何未捕获异常也转成 `error` 事件，避免流被截断。

### 5) MCP 与 Tool / Skill 服务

- `app/services/tool_service.py::execute_tool(tool_id, kwargs)` ：根据 `tool.type` 派发到 `httpx` 调用（http 工具）或 `run_in_sandbox`（code 工具）。
- `app/core/agent/tool_adapters/mcp_tools.py::load_tools(mcp)` ：桥接 `langchain-mcp-adapters` 把 MCP server 工具转 LangChain `BaseTool`，失败静默跳过（不中断整体 agent 装配）。
- `app/services/skill_service.py` ：技能本身不参与执行，只注入 `prompt` 给 LLM。

---

## 五、横向能力

- **RAG 检索内核**（`app/core/retrieval/`）：
  - `vector_search.py` / `fulltext_search.py` / `metadata_filter.py` / `navigator.py`（Tree 引导）、`reranker.py`、`rrf_merge.py`、`hybrid_retriever.py`（统一 facade）。
  - `pipeline.py` 串联；`test_metrics.py` 提供离线指标；场景配置 `app/core/scenes.py::get_scene_config(name)`。
- **元数据系统**：`KbMetadataField` + `app/services/metadata_service.py::validate_metadata` 提供 schema 校验（type / required / enum / range / regex / date）。
- **审计 / 版本 / 反馈**：`app/api/v2/audit.py`、`versions.py`（`version_diff_service.py`）、`feedback.py`。
- **可观测性**：`request_id_middleware` 全链路打点；`langsmith` / `langfuse` 切换；`execution_events` 表作为 SSE 总线。
- **存储适配**：`app/providers/storage/{base,local_fs,minio}.py` 通过 `factory.get_storage()` 选择 Local 或 MinIO。
- **安全**：`jwt.py`（access 2h / refresh 7d）、`password.py`、`crypto.py`、`init_admin.py`（首次启动建管理员）。
- **限流**：`app/core/rate_limit.py::limiter` + `slowapi`。

---

## 六、三块能力的关键流程图（对照版）

```
【文档处理】
HTTP upload ──► Document(row pending) + ParseTask(row pending)
 └─► storage.put(key) ──► PGJobQueue.enqueue_task('parse_document')
                                       │
                                       ▼
 PGWorker(轮询 SKIP LOCKED)
                                       │
   (规划中) dispatcher → parser → tree_builder → chunker → embed
                                       │
                                       ▼
                              ParseTask.status='success'
                              publish('task_complete') ──► 前端轮询进度

【工作流执行】
POST /workflows/{wid}/execute └─► arq_client.enqueue_workflow_task
 └─► PGJobQueue.enqueue →写 workflow_executions + job_queue
                                          │
                                          ▼
                                  PGWorker dequeue
                                          │
                                          ▼
 GraphBuilder.build(definition, exec_id, debug)
                                          │
                                          ▼
                          graph.stream(..., thread_id=exec_id)
                                          │
 每节点 → publish('node_complete')
 end → publish('execution_complete')
                                          │
                                          ▼
                          SSE GET /executions/{eid}/stream ──► 前端

【智能体执行】
POST /agents/{aid}/chat (question)
    └─► AgentService.chat
            ├─ build_chat_model
            ├─ build_tools(agent) ── tools/docs/wfs/skills/mcps 五源聚合
            ├─ create_react_agent(model, tools, prompt, checkpointer)
            └─ astream_events(...)
                  ├ on_tool_start  → 'tool_start'
                  ├ on_tool_end    → 'tool_end'
                  ├ on_chat_stream → 'token'
                  └ 完成 → 'done' + 更新 last_active
```

---

## 七、值得注意的实现要点 / 待完善项

1. **`_execute_parse_document` / `_execute_retrieval_test` / `enqueue_task` 仍是占位** ：只 `await asyncio.sleep(0.5)` 然后 `complete_generic('completed')`，尚未接入 dispatcher → chunker → embed 真实链路；这部分是 v0.1 的下一步。
2. **executor.py 是空模块** （注释已说明迁移到 worker）。
3. **变量插值不支持算术/函数** ：`resolve` 是纯字符串替换；`code` 节点承担复杂计算，`variable_assign` 只能做赋值。
4. **workflow 工具同步轮询 60s** ：超长工作流会被截断为"工作流执行超时"，v0.2 应改为"提交 + 订阅 SSE + 完成后回调"。
5. **Tool/Code sandbox** ：`app.providers.sandbox.run_in_sandbox` 当前 import 失败会 fallback 到本地 `exec`，仅适合 dev，生产需真实沙箱（subprocess + 资源限制 / wasm）。
6. **审计** ：有模型/服务/路由三件套，可用于全链路追踪（与 `request_id` 配合）。

---

> 下一步建议：把 `_execute_parse_document` 真实接通到 `dispatcher → tree_builder → chunker → (向量写入)`，让 v0.1 的文档-检索链路真正闭环。
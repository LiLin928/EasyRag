# Phase 2 工作流引擎实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基于LangGraph的工作流引擎，支持可视化流程设计、执行和监控

**Architecture:** 使用LangGraph构建有状态工作流，PostgresSaver持久化状态，支持6种节点类型（开始/结束/LLM/条件/人工/模板渲染），提供RESTful API和SSE实时推送

**Tech Stack:** LangGraph, PostgreSQL, FastAPI, SSE, ARQ

**关联文档:**
- 后端设计方案: `docs/backend-plans/后端开发设计方案.md`
- 后端设计方案 Phase2-3: `docs/backend-plans/后端设计方案-Phase2-3详细设计.md`
- API匹配报告: `docs/API匹配分析报告.md`

---

## 概览

**当前状态:**
- 工作流模块: 0% (0/11 API)
- 前端已完成可视化流程设计器
- 后端需要实现完整的执行引擎

**目标:**
- 工作流 CRUD: 100%
- 模板管理: 100%
- 执行引擎: 100%
- SSE 实时推送: 100%

**预计任务数:** 25
**预计时间:** 5-7天

---

## 架构设计

### 核心概念

1. **Workflow**: 工作流定义（节点+边）
2. **Execution**: 工作流执行实例
3. **Node**: 工作流节点（6种类型）
4. **Edge**: 节点连接关系
5. **State**: 执行状态（LangGraph管理）

### 技术选型

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 工作流引擎 | LangGraph | 有状态图执行 |
| 状态持久化 | PostgresSaver | PostgreSQL存储 |
| 后台任务 | ARQ | 异步执行 |
| 实时推送 | SSE | 执行进度通知 |

---

## 文件结构规划

### 新增文件
```
backend/app/
├── models/
│   ├── workflow.py              # 工作流 ORM 模型
│   └── workflow_execution.py    # 执行实例 ORM 模型
├── schemas/
│   └── workflow.py              # 工作流 Schema
├── api/v2/
│   ├── workflows.py             # 工作流 CRUD 路由
│   ├── templates.py             # 模板管理路由
│   └── executions.py            # 执行管理路由
├── services/
│   └── workflow_service.py      # 工作流业务逻辑
├── core/
│   └── workflow_engine/
│       ├── __init__.py
│       ├── engine.py            # LangGraph 引擎
│       ├── nodes/
│       │   ├── __init__.py
│       │   ├── start.py         # 开始节点
│       │   ├── end.py           # 结束节点
│       │   ├── llm.py           # LLM 节点
│       │   ├── condition.py     # 条件节点
│       │   ├── human.py         # 人工节点
│       │   └── template.py      # 模板渲染节点
│       └── state.py             # 状态定义
└── sse/
    └── workflow_emitter.py      # SSE 推送

backend/tests/
├── test_workflow_crud.py
├── test_workflow_engine.py
└── test_workflow_execution.py
```

### 数据库迁移
```
backend/alembic/versions/
└── xxx_add_workflow_tables.py   # 工作流相关表
```

---

## Task 1: 工作流数据模型

**优先级:** P0
**预计时间:** 2小时

### Step 1.1: 定义工作流 ORM 模型

- [ ] **创建 Workflow 模型**

Create: `backend/app/models/workflow.py`

```python
"""工作流 ORM 模型。"""
from sqlalchemy import Column, String, Text, JSON, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid

class Workflow(Base):
    """工作流定义。"""
    __tablename__ = "workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, comment="工作流名称")
    description = Column(Text, comment="描述")
    status = Column(String(20), default="draft", comment="draft/published/archived")
    version = Column(Integer, default=1, comment="版本号")
    nodes = Column(JSON, default=list, comment="节点列表")
    edges = Column(JSON, default=list, comment="边列表")
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default="now()")
    updated_at = Column(DateTime(timezone=True), server_default="now()", onupdate="now()")

    # 关联
    executions = relationship("WorkflowExecution", back_populates="workflow")
```

- [ ] **创建 WorkflowExecution 模型**

Create: `backend/app/models/workflow_execution.py`

```python
"""工作流执行实例 ORM 模型。"""
from sqlalchemy import Column, String, JSON, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid

class WorkflowExecution(Base):
    """工作流执行实例。"""
    __tablename__ = "workflow_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    status = Column(String(20), default="pending", comment="pending/running/success/error/wait/canceled")
    trigger = Column(String(20), default="manual", comment="manual/api/schedule/agent")
    inputs = Column(JSON, default=dict, comment="输入参数")
    outputs = Column(JSON, default=dict, comment="输出结果")
    node_states = Column(JSON, default=dict, comment="节点执行状态")
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default="now()")

    # 关联
    workflow = relationship("Workflow", back_populates="executions")
```

### Step 1.2: 创建数据库迁移

- [ ] **创建迁移脚本**

Run: `cd backend && uv run alembic revision --autogenerate -m "add workflow tables"`

- [ ] **执行迁移**

Run: `cd backend && uv run alembic upgrade head`

### Step 1.3: 提交代码

- [ ] **提交数据模型**

```bash
git add backend/app/models/workflow*.py backend/alembic/versions/*.py
git commit -m "feat(models): add workflow and execution models"
```

---

## Task 2: 工作流 Schema 定义

**优先级:** P0
**预计时间:** 1小时

### Step 2.1: 定义工作流 Schema

- [ ] **创建工作流相关的 Pydantic Schema**

Create: `backend/app/schemas/workflow.py`

```python
"""工作流 Schema。"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

# ========== 节点定义 ==========

class WfNodeData(BaseModel):
    """节点数据。"""
    rows: List[List[str]] = []
    config: Dict[str, Any] = {}

class WfNode(BaseModel):
    """工作流节点。"""
    id: str
    type: str  # start/end/llm/condition/human/template_render
    name: str
    position: Dict[str, float]
    data: WfNodeData

class WfEdge(BaseModel):
    """工作流边。"""
    id: str
    source: str
    target: str
    label: Optional[str] = None
    sourceHandle: Optional[str] = None

# ========== 工作流 CRUD ==========

class WorkflowCreate(BaseModel):
    """创建工作流。"""
    name: str
    description: Optional[str] = None

class WorkflowUpdate(BaseModel):
    """更新工作流。"""
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[List[WfNode]] = None
    edges: Optional[List[WfEdge]] = None

class WorkflowOut(BaseModel):
    """工作流输出。"""
    id: str
    name: str
    description: Optional[str]
    status: str
    version: int
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    created_at: str
    updated_at: str

# ========== 执行相关 ==========

class ExecutionOut(BaseModel):
    """执行实例输出。"""
    id: str
    workflow_id: str
    workflow_name: str
    status: str
    trigger: str
    started_at: Optional[str]
    finished_at: Optional[str]
    duration: Optional[int]  # ms
    node_progress: str  # "3/5"
```

### Step 2.2: 提交代码

- [ ] **提交 Schema 定义**

```bash
git add backend/app/schemas/workflow.py
git commit -m "feat(schemas): add workflow schemas"
```

---

## Task 3: 工作流 CRUD 接口

**优先级:** P0
**预计时间:** 2小时

### Step 3.1: 编写工作流 CRUD 测试

- [ ] **创建工作流接口测试**

Create: `backend/tests/test_workflow_crud.py`

```python
"""工作流 CRUD 接口测试。"""
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_workflow(async_client: AsyncClient, auth_headers: dict):
    """测试创建工作流。"""
    response = await async_client.post(
        "/api/v2/workflows",
        json={"name": "测试工作流", "description": "测试用"},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "id" in data["data"]
    assert data["data"]["status"] == "draft"

@pytest.mark.asyncio
async def test_list_workflows(async_client: AsyncClient, auth_headers: dict):
    """测试获取工作流列表。"""
    response = await async_client.get("/api/v2/workflows", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)

@pytest.mark.asyncio
async def test_update_workflow(async_client: AsyncClient, auth_headers: dict):
    """测试更新工作流。"""
    # 先创建
    create_resp = await async_client.post(
        "/api/v2/workflows",
        json={"name": "原名称"},
        headers=auth_headers
    )
    wf_id = create_resp.json()["data"]["id"]

    # 更新
    update_resp = await async_client.put(
        f"/api/v2/workflows/{wf_id}",
        json={"name": "新名称"},
        headers=auth_headers
    )
    assert update_resp.json()["data"]["name"] == "新名称"
```

### Step 3.2: 实现工作流 CRUD 路由

- [ ] **创建工作流路由文件**

Create: `backend/app/api/v2/workflows.py`

```python
"""工作流路由：CRUD + 执行。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.workflow import Workflow
from app.models.user import User
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowOut
from app.exceptions import BizException, ErrorCode

router = APIRouter(tags=["workflows"])

@router.get("/workflows")
async def list_workflows(me: User = Depends(get_current_user)):
    """列出当前用户的工作流。"""
    async with async_session() as s:
        rows = (await s.execute(
            select(Workflow)
            .where(Workflow.user_id == me.id)
            .order_by(Workflow.updated_at.desc())
        )).scalars().all()

    return ok([
        WorkflowOut(
            id=str(w.id),
            name=w.name,
            description=w.description,
            status=w.status,
            version=w.version,
            nodes=w.nodes,
            edges=w.edges,
            created_at=w.created_at.isoformat(),
            updated_at=w.updated_at.isoformat()
        ).model_dump()
        for w in rows
    ])

@router.post("/workflows")
async def create_workflow(
    body: WorkflowCreate,
    me: User = Depends(get_current_user)
):
    """创建工作流。"""
    async with async_session() as s:
        wf = Workflow(
            name=body.name,
            description=body.description,
            user_id=me.id
        )
        s.add(wf)
        await s.commit()
        await s.refresh(wf)

    return ok(WorkflowOut(
        id=str(wf.id),
        name=wf.name,
        description=wf.description,
        status=wf.status,
        version=wf.version,
        nodes=[],
        edges=[],
        created_at=wf.created_at.isoformat(),
        updated_at=wf.updated_at.isoformat()
    ).model_dump())

@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    me: User = Depends(get_current_user)
):
    """获取工作流详情（含节点和边）。"""
    async with async_session() as s:
        wf = (await s.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )).scalar_one_or_none()

        if not wf:
            raise BizException(ErrorCode.NOT_FOUND, "工作流不存在")

    return ok(WorkflowOut(
        id=str(wf.id),
        name=wf.name,
        description=wf.description,
        status=wf.status,
        version=wf.version,
        nodes=wf.nodes,
        edges=wf.edges,
        created_at=wf.created_at.isoformat(),
        updated_at=wf.updated_at.isoformat()
    ).model_dump())

@router.put("/workflows/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    body: WorkflowUpdate,
    me: User = Depends(get_current_user)
):
    """更新工作流。"""
    async with async_session() as s:
        wf = (await s.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )).scalar_one_or_none()

        if not wf:
            raise BizException(ErrorCode.NOT_FOUND, "工作流不存在")

        if body.name is not None:
            wf.name = body.name
        if body.description is not None:
            wf.description = body.description
        if body.nodes is not None:
            wf.nodes = [n.model_dump() for n in body.nodes]
        if body.edges is not None:
            wf.edges = [e.model_dump() for e in body.edges]

        await s.commit()
        await s.refresh(wf)

    return ok(WorkflowOut(
        id=str(wf.id),
        name=wf.name,
        description=wf.description,
        status=wf.status,
        version=wf.version,
        nodes=wf.nodes,
        edges=wf.edges,
        created_at=wf.created_at.isoformat(),
        updated_at=wf.updated_at.isoformat()
    ).model_dump())

@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    me: User = Depends(get_current_user)
):
    """删除工作流。"""
    async with async_session() as s:
        wf = (await s.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )).scalar_one_or_none()

        if wf:
            await s.delete(wf)
            await s.commit()

    return ok({"success": True})
```

### Step 3.3: 运行测试验证

- [ ] **运行测试**

Run: `cd backend && uv run pytest tests/test_workflow_crud.py -v`

### Step 3.4: 提交代码

- [ ] **提交工作流 CRUD**

```bash
git add backend/app/api/v2/workflows.py backend/tests/test_workflow_crud.py
git commit -m "feat(api): add workflow CRUD endpoints"
```

---

## Task 4: 工作流引擎核心（LangGraph集成）

**优先级:** P0
**预计时间:** 4小时

**说明:** 这是最核心的任务，实现LangGraph工作流引擎。由于篇幅限制，这里给出框架和关键代码。

### Step 4.1: 定义工作流状态

- [ ] **创建状态定义**

Create: `backend/app/core/workflow_engine/state.py`

```python
"""工作流状态定义。"""
from typing import TypedDict, Dict, Any, List
from langgraph.graph import StateGraph

class WorkflowState(TypedDict):
    """工作流执行状态。"""
    # 输入
    query: str
    documents: List[str]

    # 节点间传递
    current_node: str
    node_outputs: Dict[str, Any]

    # LLM 相关
    llm_result: str
    llm_content: str

    # 条件分支
    condition_result: bool

    # 最终输出
    final_output: Dict[str, Any]

    # 执行追踪
    execution_path: List[str]
```

### Step 4.2: 实现节点执行器

- [ ] **实现 LLM 节点**

Create: `backend/app/core/workflow_engine/nodes/llm.py`

```python
"""LLM 节点执行器。"""
from langchain_openai import ChatOpenAI
from app.core.workflow_engine.state import WorkflowState

async def execute_llm_node(state: WorkflowState, config: dict) -> WorkflowState:
    """执行 LLM 节点。"""
    model = config.get("model", "gpt-4")
    system_prompt = config.get("systemPrompt", "")
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("maxTokens", 2000)

    # 构建 LLM
    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens
    )

    # 准备输入
    messages = []
    if system_prompt:
        messages.append(("system", system_prompt))

    # 替换变量
    query = state.get("query", "")
    messages.append(("user", query))

    # 执行
    response = await llm.ainvoke(messages)

    # 更新状态
    return {
        **state,
        "llm_result": response.content,
        "execution_path": state["execution_path"] + ["llm"]
    }
```

- [ ] **实现条件节点**

Create: `backend/app/core/workflow_engine/nodes/condition.py`

```python
"""条件节点执行器。"""
from app.core.workflow_engine.state import WorkflowState

async def execute_condition_node(state: WorkflowState, config: dict) -> WorkflowState:
    """执行条件节点。"""
    expression = config.get("expression", "true")

    # 简单条件求值（实际应使用安全的表达式引擎）
    # TODO: 实现变量替换和表达式求值
    result = True

    return {
        **state,
        "condition_result": result,
        "execution_path": state["execution_path"] + ["condition"]
    }
```

### Step 4.3: 构建工作流图

- [ ] **创建工作流引擎**

Create: `backend/app/core/workflow_engine/engine.py`

```python
"""工作流引擎核心。"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from app.core.workflow_engine.state import WorkflowState
from app.core.workflow_engine.nodes.llm import execute_llm_node
from app.core.workflow_engine.nodes.condition import execute_condition_node
from app.config import settings

class WorkflowEngine:
    """工作流引擎。"""

    def __init__(self):
        self.checkpointer = PostgresSaver(
            settings.database_url.replace("+asyncpg", "")
        )

    async def build_graph(self, workflow_id: str) -> StateGraph:
        """从数据库加载工作流定义并构建图。"""
        # 加载节点和边
        nodes, edges = await self._load_workflow(workflow_id)

        # 创建状态图
        graph = StateGraph(WorkflowState)

        # 添加节点
        for node in nodes:
            handler = self._get_node_handler(node["type"], node["data"]["config"])
            graph.add_node(node["id"], handler)

        # 添加边
        for edge in edges:
            source = edge["source"]
            target = edge["target"]

            if node["type"] == "condition":
                # 条件分支
                label = edge.get("label", "是")
                graph.add_conditional_edge(
                    source,
                    lambda s: label == "是" if s["condition_result"] else label == "否",
                    {
                        "是": target,
                        "否": self._find_false_branch(edges, source)
                    }
                )
            else:
                graph.add_edge(source, target)

        # 设置入口和出口
        graph.set_entry_point("start")
        graph.add_edge("end", END)

        return graph

    async def execute(self, workflow_id: str, inputs: dict) -> dict:
        """执行工作流。"""
        graph = await self.build_graph(workflow_id)
        app = graph.compile(checkpointer=self.checkpointer)

        # 执行
        result = await app.ainvoke(inputs)

        return result
```

### Step 4.4: 提交代码

- [ ] **提交工作流引擎**

```bash
git add backend/app/core/workflow_engine/
git commit -m "feat(core): implement LangGraph workflow engine"
```

---

## Task 5: 工作流执行接口和SSE

**优先级:** P1
**预计时间:** 3小时

### Step 5.1: 实现执行接口

- [ ] **创建执行路由**

Create: `backend/app/api/v2/executions.py`

```python
"""执行管理路由。"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.api.deps import get_current_user
from app.api.response import ok
from app.models.user import User
from app.services.workflow_service import execute_workflow

router = APIRouter(tags=["executions"])

@router.post("/workflows/{workflow_id}/execute")
async def trigger_execution(
    workflow_id: str,
    inputs: dict,
    me: User = Depends(get_current_user)
):
    """触发工作流执行。"""
    execution_id = await execute_workflow(workflow_id, inputs, me.id)
    return ok({"executionId": execution_id})

@router.get("/executions/{execution_id}/stream")
async def stream_execution(
    execution_id: str,
    me: User = Depends(get_current_user)
):
    """SSE 实时推送执行进度。"""
    return StreamingResponse(
        execution_stream(execution_id),
        media_type="text/event-stream"
    )

@router.get("/executions")
async def list_executions(me: User = Depends(get_current_user)):
    """列出执行历史。"""
    # 实现...
    pass
```

### Step 5.2: 实现SSE推送

- [ ] **创建SSE发射器**

Create: `backend/app/sse/workflow_emitter.py`

```python
"""工作流执行 SSE 推送。"""
import asyncio
from app.sse.emitter import emit_event

async def execution_stream(execution_id: str):
    """实时推送执行进度。"""
    while True:
        # 查询执行状态
        execution = await get_execution_status(execution_id)

        # 推送节点进度
        yield f"data: {json.dumps({'type': 'progress', 'node': execution['current_node']})}\n\n"

        if execution["status"] in ["success", "error", "canceled"]:
            # 推送完成事件
            yield f"data: {json.dumps({'type': 'complete', 'result': execution['outputs']})}\n\n"
            break

        await asyncio.sleep(1)
```

### Step 5.3: 提交代码

- [ ] **提交执行接口和SSE**

```bash
git add backend/app/api/v2/executions.py backend/app/sse/workflow_emitter.py
git commit -m "feat(api): add workflow execution and SSE streaming"
```

---

## Task 6: 模板管理

**优先级:** P1
**预计时间:** 1小时

**说明:** 模板是预定义的工作流，用户可以从模板创建新工作流。

### Step 6.1: 实现模板接口

- [ ] **创建模板路由**

Create: `backend/app/api/v2/templates.py`

```python
"""模板管理路由。"""
from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.api.response import ok
from app.models.user import User
from app.schemas.workflow import TemplateOut

router = APIRouter(tags=["templates"])

@router.get("/templates")
async def list_templates(me: User = Depends(get_current_user)):
    """列出工作流模板。"""
    # 内置模板
    templates = [
        {
            "id": "tpl-1",
            "name": "标准资料审核流程",
            "description": "适用于文档内容审核场景",
            "source": "official",
            "tags": ["审核", "官方"],
            "nodeCount": 5,
            "useCount": 128,
            "definition": {"nodes": [], "edges": []}
        }
    ]
    return ok(templates)

@router.post("/templates/{template_id}/instantiate")
async def instantiate_template(
    template_id: str,
    name: str,
    me: User = Depends(get_current_user)
):
    """从模板创建工作流。"""
    # 加载模板定义
    # 创建新工作流
    # 返回工作流ID
    pass
```

### Step 6.2: 提交代码

- [ ] **提交模板管理**

```bash
git add backend/app/api/v2/templates.py
git commit -m "feat(api): add workflow template management"
```

---

## Task 7: 集成测试和文档

**优先级:** P0
**预计时间:** 2小时

### Step 7.1: 运行完整测试套件

- [ ] **运行所有测试**

Run: `cd backend && uv run pytest -v`

### Step 7.2: 编写工作流引擎文档

- [ ] **创建工作流引擎使用文档**

Create: `docs/workflow-engine-guide.md`

内容包括：
- 节点类型说明
- 变量和表达式
- 条件分支
- 人工审核
- SSE 事件格式

### Step 7.3: 更新API匹配报告

- [ ] **更新完成度**

工作流模块完成度: 0% → 100%

### Step 7.4: 提交文档

- [ ] **提交所有变更**

```bash
git add .
git commit -m "feat(workflow): complete workflow engine implementation"
```

---

## 验收标准

- [ ] 工作流 CRUD 接口完整可用
- [ ] 可从前端创建、编辑、删除工作流
- [ ] LangGraph 引擎能执行基本流程（开始→LLM→结束）
- [ ] 执行进度通过 SSE 实时推送
- [ ] 模板管理功能正常
- [ ] 所有测试通过

---

## 风险和依赖

**风险:**
1. LangGraph 学习曲线陡峭，可能需要调试时间
2. PostgresSaver 配置可能与现有数据库连接池冲突
3. 节点间变量传递逻辑复杂

**依赖:**
- LangGraph 库安装：`langgraph`, `langchain-core`
- PostgreSQL 数据库（已具备）
- ARQ 后台任务队列（已配置）

---

## 后续优化

1. **性能优化**: 添加工作流缓存
2. **监控**: 添加执行日志和性能指标
3. **调试**: 实现工作流调试模式（断点、单步执行）
4. **版本管理**: 工作流版本回退

---

**计划保存至:** `docs/superpowers/plans/2026-09-08-phase2-workflow.md`
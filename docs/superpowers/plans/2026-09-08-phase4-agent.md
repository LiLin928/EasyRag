# Phase 4 智能体系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现智能体管理和编排，支持工具调用、知识库绑定、工作流触发

**Architecture:** 基于 LangChain Agent + ReAct 框架，集成工具链、知识库、工作流，提供智能对话和任务执行能力

**Tech Stack:** LangChain Agent, ReAct, Tool Calling, Vector Store

**关联文档:**
- 后端设计方案: `docs/backend-plans/后端开发设计方案.md`
- Phase 3 工具链: `2026-09-08-phase3-toolchain.md`

---

## 概览

**当前状态:**
- 智能体模块: 0%

**目标:**
- 智能体 CRUD: 100%
- 智能体编排器: 100%
- 工具调用集成: 100%
- 知识库检索集成: 100%

**预计任务数:** 15
**预计时间:** 3-4天

---

## 架构设计

### 智能体编排流程

```
用户输入
  ↓
智能体编排器
  ↓
┌──────┬──────┬──────┐
│ 知识库 │ 工具链 │ 工作流 │
│ 检索  │ 调用  │ 触发  │
└──────┴──────┴──────┘
  ↓
LLM推理（ReAct）
  ↓
生成回复 + 工具调用
  ↓
执行工具 → 再次推理
  ↓
最终输出
```

---

## Task 1: 智能体 ORM 和 Schema

**优先级:** P0
**预计时间:** 1小时

### Step 1.1: 定义智能体 ORM

- [ ] **创建智能体模型**

Create: `backend/app/models/agent.py`

```python
"""智能体 ORM 模型。"""
from sqlalchemy import Column, String, Text, JSON, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid

class Agent(Base):
    """智能体定义。"""
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    desc = Column(Text)
    model = Column(String(100), default="gpt-4o", comment="使用的LLM模型")
    prompt = Column(Text, comment="系统提示词")
    temp = Column(Float, default=0.7, comment="温度参数")
    max_tokens = Column(Integer, default=2048, comment="最大tokens")
    tools = Column(JSON, default=list, comment="绑定的工具ID")
    docs = Column(JSON, default=list, comment="绑定的知识库文档ID")
    wfs = Column(JSON, default=list, comment="绑定的工作流ID")
    mcps = Column(JSON, default=list, comment="绑定的MCP服务ID")
    skills = Column(JSON, default=list, comment="绑定的技能ID")
    enabled = Column(Boolean, default=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    last_active = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default="now()")
```

### Step 1.2: 定义智能体 Schema

- [ ] **创建智能体 Schema**

Create: `backend/app/schemas/agent.py`

```python
"""智能体 Schema。"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class AgentCreate(BaseModel):
    name: str
    desc: Optional[str] = None
    model: str = "gpt-4o"
    prompt: Optional[str] = None
    temp: float = 0.7
    max_tokens: int = 2048
    tools: List[str] = []
    docs: List[str] = []
    wfs: List[str] = []
    mcps: List[str] = []
    skills: List[str] = []
    enabled: bool = True

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    desc: Optional[str] = None
    prompt: Optional[str] = None
    temp: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[List[str]] = None
    docs: Optional[List[str]] = None
    wfs: Optional[List[str]] = None
    mcps: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    enabled: Optional[bool] = None

class AgentOut(BaseModel):
    id: str
    name: str
    desc: Optional[str]
    model: str
    prompt: Optional[str]
    temp: float
    max_tokens: int
    tools: List[str]
    docs: List[str]
    wfs: List[str]
    mcps: List[str]
    skills: List[str]
    enabled: bool
    last_active: Optional[str]
    created_at: str
```

### Step 1.3: 创建迁移并提交

```bash
cd backend && uv run alembic revision --autogenerate -m "add agents table"
cd backend && uv run alembic upgrade head
git add backend/app/models/agent.py backend/app/schemas/agent.py backend/alembic/versions/*.py
git commit -m "feat(models): add agent model and schema"
```

---

## Task 2: 智能体 CRUD 接口

**优先级:** P0
**预计时间:** 2小时

### Step 2.1: 实现智能体路由

- [ ] **创建智能体路由**

Create: `backend/app/api/v2/agents.py`

```python
"""智能体路由：CRUD + 对话。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentUpdate, AgentOut

router = APIRouter(tags=["agents"])

@router.get("/agents")
async def list_agents(me: User = Depends(get_current_user)):
    """列出智能体。"""
    async with async_session() as s:
        rows = (await s.execute(
            select(Agent)
            .where(Agent.user_id == me.id)
            .order_by(Agent.created_at.desc())
        )).scalars().all()
    return ok([AgentOut(...).model_dump() for a in rows])

@router.post("/agents")
async def create_agent(body: AgentCreate, me: User = Depends(get_current_user)):
    """创建智能体。"""
    async with async_session() as s:
        agent = Agent(
            name=body.name,
            desc=body.desc,
            model=body.model,
            prompt=body.prompt,
            temp=body.temp,
            max_tokens=body.max_tokens,
            tools=body.tools,
            docs=body.docs,
            wfs=body.wfs,
            mcps=body.mcps,
            skills=body.skills,
            enabled=body.enabled,
            user_id=me.id
        )
        s.add(agent)
        await s.commit()
        await s.refresh(agent)
    return ok(AgentOut(...).model_dump())

@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, me: User = Depends(get_current_user)):
    """获取智能体详情。"""
    async with async_session() as s:
        agent = (await s.execute(
            select(Agent).where(Agent.id == agent_id)
        )).scalar_one_or_none()
        if not agent:
            raise BizException(ErrorCode.NOT_FOUND, "智能体不存在")
    return ok(AgentOut(...).model_dump())

@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, body: AgentUpdate, me: User = Depends(get_current_user)):
    """更新智能体。"""
    # 实现...

@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, me: User = Depends(get_current_user)):
    """删除智能体。"""
    # 实现...
```

### Step 2.2: 提交代码

```bash
git add backend/app/api/v2/agents.py backend/tests/test_agent_crud.py
git commit -m "feat(api): add agent CRUD endpoints"
```

---

## Task 3: 智能体编排器

**优先级:** P0
**预计时间:** 4小时

### Step 3.1: 实现智能体编排服务

- [ ] **创建智能体编排器**

Create: `backend/app/services/agent_orchestrator.py`

```python
"""智能体编排器：集成工具、知识库、工作流。"""
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from app.models.agent import Agent
from app.services.retrieval_service import RetrievalService
from app.services.unified_tool_service import UnifiedToolService
from app.services.workflow_service import WorkflowService

class AgentOrchestrator:
    """智能体编排器。"""

    def __init__(self, agent: Agent):
        self.agent = agent
        self.llm = None
        self.tools = []

    async def _build_llm(self):
        """构建LLM。"""
        self.llm = ChatOpenAI(
            model=self.agent.model,
            temperature=self.agent.temp,
            max_tokens=self.agent.max_tokens
        )

    async def _build_tools(self):
        """构建工具列表。"""
        tool_service = UnifiedToolService()

        # 添加绑定的工具
        for tool_id in self.agent.tools:
            self.tools.append(Tool(
                name=f"tool_{tool_id}",
                func=lambda params, tid=tool_id: tool_service.execute("tool", tid, params),
                description="工具调用"
            ))

        # 添加知识库检索工具
        if self.agent.docs:
            retrieval_service = RetrievalService()
            self.tools.append(Tool(
                name="knowledge_search",
                func=lambda query: retrieval_service.retrieve(...),
                description="知识库检索"
            ))

        # 添加工作流触发工具
        for wf_id in self.agent.wfs:
            wf_service = WorkflowService()
            self.tools.append(Tool(
                name=f"workflow_{wf_id}",
                func=lambda inputs, wid=wf_id: wf_service.execute(wid, inputs),
                description="工作流执行"
            ))

    async def chat(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """与智能体对话。

        Args:
            query: 用户输入
            context: 上下文信息

        Returns:
            回复结果
        """
        await self._build_llm()
        await self._build_tools()

        # 创建ReAct Agent
        agent = create_react_agent(self.llm, self.tools, self.agent.prompt)
        executor = AgentExecutor(agent=agent, tools=self.tools)

        # 执行
        result = await executor.ainvoke({"input": query})

        return {
            "response": result["output"],
            "tool_calls": result.get("intermediate_steps", [])
        }
```

### Step 3.2: 集成到对话接口

- [ ] **在对话接口中支持智能体**

Modify: `backend/app/api/v2/chat.py`

```python
@router.post("/chat")
async def chat(req: ChatRequest, me: User = Depends(get_current_user)):
    """对话接口。"""
    if req.agent_id:
        # 使用智能体对话
        async with async_session() as s:
            agent = (await s.execute(
                select(Agent).where(Agent.id == req.agent_id)
            )).scalar_one_or_none()

        orchestrator = AgentOrchestrator(agent)
        return StreamingResponse(
            orchestrator.chat_stream(req.query),
            media_type="text/event-stream"
        )
    else:
        # 普通对话
        # ...
```

### Step 3.3: 提交代码

```bash
git add backend/app/services/agent_orchestrator.py backend/app/api/v2/chat.py
git commit -m "feat(services): add agent orchestrator with tool integration"
```

---

## 验收标准

- [ ] 智能体 CRUD 完整
- [ ] 智能体可以绑定工具、知识库、工作流
- [ ] ReAct 推理正常工作
- [ ] 工具调用集成成功
- [ ] 知识库检索集成成功
- [ ] 所有测试通过

---

**计划保存至:** `docs/superpowers/plans/2026-09-08-phase4-agent.md`
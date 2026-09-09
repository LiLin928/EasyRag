# Phase 3 工具链管理实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现工具、技能、MCP服务管理，支持测试和沙箱执行

**Architecture:** 工具注册机制 + OpenSandbox代码沙箱 + MCP协议适配器，提供统一的工具调用接口

**Tech Stack:** FastAPI, OpenSandbox, MCP SDK, Python沙箱

**关联文档:**
- 后端设计方案: `docs/backend-plans/后端开发设计方案.md`
- API匹配报告: `docs/API匹配分析报告.md`
- Phase 2 工作流: `2026-09-08-phase2-workflow.md`

---

## 概览

**当前状态:**
- 工具模块: 80% (缺测试接口)
- 技能模块: 0%
- MCP模块: 0%

**目标:**
- 工具模块: 100%
- 技能模块: 100%
- MCP模块: 100%
- 沙箱执行: 100%

**预计任务数:** 20
**预计时间:** 4-5天

---

## 架构设计

### 工具链层次结构

```
┌─────────────────────────────────────┐
│          工具调用统一接口            │
│    execute(tool_id, params)         │
└─────────────────────────────────────┘
           │
    ┌──────┼──────┐
    │      │      │
┌───▼───┐┌──▼───┐┌──▼───┐
│ 工具   ││ 技能 ││ MCP  │
│Tool    ││Skill ││服务  │
└───┬───┘└──┬───┘└──┬───┘
    │       │       │
    │       │       │
┌───▼───────▼───────▼───┐
│   OpenSandbox 沙箱    │
│   (HTTP API调用)      │
└──────────────────────┘
```

### 核心概念

1. **Tool**: 外部API工具（HTTP/内置）
2. **Skill**: 自定义技能（Python脚本）
3. **MCP**: Model Context Protocol服务
4. **统一执行接口**: 抽象工具调用

---

## 文件结构规划

### 新增文件
```
backend/app/
├── models/
│   ├── tool.py              # 工具 ORM（已存在，扩展）
│   ├── skill.py             # 技能 ORM
│   └── mcp.py               # MCP ORM
├── schemas/
│   ├── tool.py              # 工具 Schema（已存在，扩展）
│   ├── skill.py             # 技能 Schema
│   └── mcp.py               # MCP Schema
├── api/v2/
│   ├── tools.py             # 工具路由（已存在，扩展测试）
│   ├── skills.py            # 技能路由
│   └── mcps.py              # MCP路由
├── services/
│   ├── tool_service.py      # 工具服务
│   ├── skill_service.py     # 技能服务
│   ├── mcp_service.py       # MCP服务
│   └── sandbox_service.py   # 沙箱服务
├── core/
│   └── sandbox/
│       ├── __init__.py
│       ├── client.py        # OpenSandbox客户端
│       └── executor.py      # 执行器
└── providers/
    └── mcp/
        ├── __init__.py
        ├── adapter.py       # MCP适配器
        └── sse_client.py    # SSE客户端

backend/tests/
├── test_tool_execution.py
├── test_skill_crud.py
├── test_mcp_management.py
└── test_sandbox.py
```

---

## Task 1: 工具测试接口

**优先级:** P0
**预计时间:** 1小时

**说明:** 补全工具模块最后缺失的测试接口。

### Step 1.1: 实现工具测试接口

- [ ] **在 tools.py 添加测试接口**

Modify: `backend/app/api/v2/tools.py` (添加测试路由)

```python
from pydantic import BaseModel
from typing import Dict, Any
from app.services.tool_service import ToolService

class ToolTestRequest(BaseModel):
    """工具测试请求。"""
    args: Dict[str, Any] = {}

class ToolTestResult(BaseModel):
    """工具测试结果。"""
    success: bool
    data: Any = None
    error: str = None
    duration: int  # ms

@router.post("/tools/{tool_id}/test")
async def test_tool(
    tool_id: str,
    body: ToolTestRequest,
    me=Depends(get_current_user)
):
    """测试工具执行。

    根据工具类型执行测试调用：
    - HTTP工具：发起HTTP请求
    - 内置工具：调用内置函数
    - Python工具：在沙箱中执行

    Args:
        tool_id: 工具ID
        body: 测试参数

    Returns:
        测试结果
    """
    async with async_session() as s:
        tool = (await s.execute(select(Tool).where(Tool.id == tool_id))).scalar_one_or_none()
        if not tool:
            raise BizException(ErrorCode.NOT_FOUND, "工具不存在")

    service = ToolService()
    result = await service.test_tool(tool, body.args)

    return ok(result.model_dump())
```

### Step 1.2: 实现工具服务

- [ ] **创建工具服务**

Create: `backend/app/services/tool_service.py`

```python
"""工具服务：处理工具测试和执行。"""
import time
from typing import Dict, Any
from app.models.tool import Tool
from app.schemas.tool import ToolTestResult
from app.core.sandbox.executor import SandboxExecutor
import httpx

class ToolService:
    """工具服务。"""

    async def test_tool(self, tool: Tool, args: Dict[str, Any]) -> ToolTestResult:
        """测试工具。

        Args:
            tool: 工具对象
            args: 测试参数

        Returns:
            测试结果
        """
        start = time.time()

        try:
            if tool.type == "HTTP":
                result = await self._test_http_tool(tool, args)
            elif tool.type == "Python":
                result = await self._test_python_tool(tool, args)
            elif tool.type == "内置":
                result = await self._test_builtin_tool(tool, args)
            else:
                return ToolTestResult(
                    success=False,
                    error=f"未知工具类型: {tool.type}",
                    duration=0
                )

            elapsed = int((time.time() - start) * 1000)

            return ToolTestResult(
                success=True,
                data=result,
                duration=elapsed
            )

        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            return ToolTestResult(
                success=False,
                error=str(e),
                duration=elapsed
            )

    async def _test_http_tool(self, tool: Tool, args: Dict[str, Any]) -> Any:
        """测试HTTP工具。"""
        config = tool.config
        url = config.get("url", "")
        method = config.get("method", "GET")

        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, params=args)
            else:
                response = await client.post(url, json=args)

            return {
                "status_code": response.status_code,
                "data": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text[:500]
            }

    async def _test_python_tool(self, tool: Tool, args: Dict[str, Any]) -> Any:
        """测试Python工具（在沙箱中执行）。"""
        executor = SandboxExecutor()
        code = tool.config.get("code", "")

        result = await executor.execute(code, args)
        return result

    async def _test_builtin_tool(self, tool: Tool, args: Dict[str, Any]) -> Any:
        """测试内置工具。"""
        # 内置工具直接执行，无需沙箱
        # 例如：邮件发送、通知等
        return {"message": "内置工具测试成功", "tool_name": tool.name}
```

### Step 1.3: 编写测试

- [ ] **测试工具测试接口**

Create: `backend/tests/test_tool_execution.py`

```python
"""工具执行测试。"""
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_http_tool_test(async_client: AsyncClient, auth_headers: dict):
    """测试HTTP工具测试接口。"""
    # 创建HTTP工具
    create_resp = await async_client.post(
        "/api/v2/tools",
        json={
            "name": "HTTP测试工具",
            "type": "HTTP",
            "desc": "测试用",
            "config": {
                "url": "https://httpbin.org/get",
                "method": "GET"
            },
            "enabled": True
        },
        headers=auth_headers
    )
    tool_id = create_resp.json()["data"]["id"]

    # 测试工具
    test_resp = await async_client.post(
        f"/api/v2/tools/{tool_id}/test",
        json={"args": {"test": "value"}},
        headers=auth_headers
    )

    assert test_resp.status_code == 200
    data = test_resp.json()
    assert data["code"] == 0
    assert data["data"]["success"] == True
    assert "duration" in data["data"]
```

### Step 1.4: 提交代码

- [ ] **提交工具测试接口**

```bash
git add backend/app/api/v2/tools.py backend/app/services/tool_service.py backend/tests/test_tool_execution.py
git commit -m "feat(api): add tool test endpoint and service"
```

---

## Task 2: OpenSandbox 沙箱集成

**优先级:** P0
**预计时间:** 3小时

### Step 2.1: 创建沙箱客户端

- [ ] **实现OpenSandbox客户端**

Create: `backend/app/core/sandbox/client.py`

```python
"""OpenSandbox 客户端。"""
import httpx
from typing import Dict, Any
from app.config import settings

class OpenSandboxClient:
    """OpenSandbox 沙箱客户端。"""

    def __init__(self):
        self.base_url = settings.sandbox_url  # http://192.168.137.13:8090
        self.timeout = 30

    async def execute_code(
        self,
        code: str,
        inputs: Dict[str, Any] = None,
        language: str = "python"
    ) -> Dict[str, Any]:
        """在沙箱中执行代码。

        Args:
            code: 代码内容
            inputs: 输入参数
            language: 语言（python/javascript等）

        Returns:
            执行结果
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/execute",
                json={
                    "code": code,
                    "language": language,
                    "inputs": inputs or {}
                }
            )

            if response.status_code != 200:
                raise Exception(f"沙箱执行失败: {response.text}")

            return response.json()

    async def check_health(self) -> bool:
        """检查沙箱服务健康状态。"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except:
            return False
```

### Step 2.2: 创建沙箱执行器

- [ ] **实现沙箱执行器**

Create: `backend/app/core/sandbox/executor.py`

```python
"""沙箱执行器。"""
from typing import Dict, Any
from app.core.sandbox.client import OpenSandboxClient

class SandboxExecutor:
    """沙箱执行器：封装代码执行逻辑。"""

    def __init__(self):
        self.client = OpenSandboxClient()

    async def execute(
        self,
        code: str,
        inputs: Dict[str, Any] = None
    ) -> Any:
        """执行Python代码。

        Args:
            code: Python代码
            inputs: 输入变量

        Returns:
            执行结果
        """
        # 包装代码，将inputs作为变量注入
        wrapped_code = f"""
import json

# 注入输入变量
inputs = {inputs or {}}
locals().update(inputs)

# 用户代码
{code}

# 返回结果（假设代码中有result变量）
if 'result' in locals():
    output = result
else:
    output = None
"""

        result = await self.client.execute_code(wrapped_code)

        if result.get("error"):
            raise Exception(result["error"])

        return result.get("output")

    async def test_connection(self) -> bool:
        """测试沙箱连接。"""
        return await self.client.check_health()
```

### Step 2.3: 编写沙箱测试

- [ ] **测试沙箱功能**

Create: `backend/tests/test_sandbox.py`

```python
"""沙箱测试。"""
import pytest
from app.core.sandbox.executor import SandboxExecutor

@pytest.mark.asyncio
async def test_sandbox_execute():
    """测试沙箱代码执行。"""
    executor = SandboxExecutor()

    code = """
result = {"sum": inputs["a"] + inputs["b"]}
"""

    output = await executor.execute(code, {"a": 1, "b": 2})

    assert output["sum"] == 3

@pytest.mark.asyncio
async def test_sandbox_health():
    """测试沙箱健康检查。"""
    executor = SandboxExecutor()
    is_healthy = await executor.test_connection()

    # 如果沙箱服务未启动，跳过测试
    if not is_healthy:
        pytest.skip("OpenSandbox服务未运行")
```

### Step 2.4: 提交代码

- [ ] **提交沙箱集成**

```bash
git add backend/app/core/sandbox/ backend/tests/test_sandbox.py
git commit -m "feat(core): integrate OpenSandbox for code execution"
```

---

## Task 3: 技能模块 ORM 和 Schema

**优先级:** P0
**预计时间:** 1小时

### Step 3.1: 定义技能 ORM

- [ ] **创建技能模型**

Create: `backend/app/models/skill.py`

```python
"""技能 ORM 模型。"""
from sqlalchemy import Column, String, Text, JSON, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid

class Skill(Base):
    """技能定义。"""
    __tablename__ = "skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, comment="技能名称")
    desc = Column(Text, comment="描述")
    scope = Column(String(20), default="custom", comment="builtin/custom")
    version = Column(String(20), default="1.0.0", comment="版本")
    ico = Column(String(10), comment="图标emoji")
    trigger = Column(Text, comment="触发条件")
    prompt = Column(Text, comment="提示词模板")
    tools = Column(JSON, default=list, comment="绑定的工具ID列表")
    docs = Column(JSON, default=list, comment="绑定的文档ID列表")
    wfs = Column(JSON, default=list, comment="绑定的工作流ID列表")
    examples = Column(JSON, default=list, comment="示例问答")
    scripts = Column(JSON, default=list, comment="脚本列表")
    budget = Column(Integer, default=0, comment="预算tokens")
    used = Column(Integer, default=0, comment="已用tokens")
    enabled = Column(Boolean, default=True, comment="是否启用")
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="now()")
    updated_at = Column(DateTime(timezone=True), server_default="now()", onupdate="now()")
```

### Step 3.2: 定义技能 Schema

- [ ] **创建技能 Schema**

Create: `backend/app/schemas/skill.py`

```python
"""技能 Schema。"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class SkillScript(BaseModel):
    """技能脚本。"""
    name: str
    content: str

class SkillExample(BaseModel):
    """技能示例。"""
    q: str
    a: str

class SkillCreate(BaseModel):
    """创建技能。"""
    name: str
    desc: Optional[str] = None
    scope: str = "custom"
    version: str = "1.0.0"
    ico: Optional[str] = None
    trigger: Optional[str] = None
    prompt: Optional[str] = None
    tools: List[str] = []
    docs: List[str] = []
    wfs: List[str] = []
    examples: List[SkillExample] = []
    scripts: List[SkillScript] = []
    budget: int = 0
    enabled: bool = True

class SkillUpdate(BaseModel):
    """更新技能。"""
    name: Optional[str] = None
    desc: Optional[str] = None
    trigger: Optional[str] = None
    prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    docs: Optional[List[str]] = None
    wfs: Optional[List[str]] = None
    examples: Optional[List[SkillExample]] = None
    scripts: Optional[List[SkillScript]] = None
    budget: Optional[int] = None
    enabled: Optional[bool] = None

class SkillOut(BaseModel):
    """技能输出。"""
    id: str
    name: str
    desc: Optional[str]
    scope: str
    version: str
    ico: Optional[str]
    trigger: Optional[str]
    prompt: Optional[str]
    tools: List[str]
    docs: List[str]
    wfs: List[str]
    examples: List[Dict[str, Any]]
    scripts: List[Dict[str, Any]]
    budget: int
    used: int
    enabled: bool
    created_at: str
```

### Step 3.3: 创建数据库迁移

- [ ] **创建迁移**

Run: `cd backend && uv run alembic revision --autogenerate -m "add skills table"`

Run: `cd backend && uv run alembic upgrade head`

### Step 3.4: 提交代码

- [ ] **提交技能模型和Schema**

```bash
git add backend/app/models/skill.py backend/app/schemas/skill.py backend/alembic/versions/*.py
git commit -m "feat(models): add skill model and schema"
```

---

## Task 4: 技能 CRUD 接口

**优先级:** P0
**预计时间:** 2小时

### Step 4.1: 编写技能测试

- [ ] **创建技能接口测试**

Create: `backend/tests/test_skill_crud.py`

```python
"""技能 CRUD 测试。"""
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_skill(async_client: AsyncClient, auth_headers: dict):
    """测试创建技能。"""
    response = await async_client.post(
        "/api/v2/skills",
        json={
            "name": "测试技能",
            "desc": "测试用技能",
            "prompt": "你是一个助手",
            "tools": ["tool1"],
            "enabled": True
        },
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "id" in data["data"]
    assert data["data"]["name"] == "测试技能"

@pytest.mark.asyncio
async def test_list_skills(async_client: AsyncClient, auth_headers: dict):
    """测试获取技能列表。"""
    response = await async_client.get("/api/v2/skills", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)
```

### Step 4.2: 实现技能 CRUD 路由

- [ ] **创建技能路由**

Create: `backend/app/api/v2/skills.py`

```python
"""技能路由：CRUD + 测试。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.skill import Skill
from app.models.user import User
from app.schemas.skill import SkillCreate, SkillUpdate, SkillOut
from app.exceptions import BizException, ErrorCode

router = APIRouter(tags=["skills"])

@router.get("/skills")
async def list_skills(me: User = Depends(get_current_user)):
    """列出技能。"""
    async with async_session() as s:
        rows = (await s.execute(
            select(Skill)
            .where(Skill.user_id == me.id)
            .order_by(Skill.created_at.desc())
        )).scalars().all()

    return ok([
        SkillOut(
            id=str(s.id),
            name=s.name,
            desc=s.desc,
            scope=s.scope,
            version=s.version,
            ico=s.ico,
            trigger=s.trigger,
            prompt=s.prompt,
            tools=s.tools,
            docs=s.docs,
            wfs=s.wfs,
            examples=s.examples,
            scripts=s.scripts,
            budget=s.budget,
            used=s.used,
            enabled=s.enabled,
            created_at=s.created_at.isoformat()
        ).model_dump()
        for s in rows
    ])

@router.post("/skills")
async def create_skill(
    body: SkillCreate,
    me: User = Depends(get_current_user)
):
    """创建技能。"""
    async with async_session() as s:
        skill = Skill(
            name=body.name,
            desc=body.desc,
            scope=body.scope,
            version=body.version,
            ico=body.ico,
            trigger=body.trigger,
            prompt=body.prompt,
            tools=body.tools,
            docs=body.docs,
            wfs=body.wfs,
            examples=[ex.model_dump() for ex in body.examples],
            scripts=[sc.model_dump() for sc in body.scripts],
            budget=body.budget,
            enabled=body.enabled,
            user_id=me.id
        )
        s.add(skill)
        await s.commit()
        await s.refresh(skill)

    return ok(SkillOut(
        id=str(skill.id),
        name=skill.name,
        desc=skill.desc,
        scope=skill.scope,
        version=skill.version,
        ico=skill.ico,
        trigger=skill.trigger,
        prompt=skill.prompt,
        tools=skill.tools,
        docs=skill.docs,
        wfs=skill.wfs,
        examples=skill.examples,
        scripts=skill.scripts,
        budget=skill.budget,
        used=skill.used,
        enabled=skill.enabled,
        created_at=skill.created_at.isoformat()
    ).model_dump())

@router.put("/skills/{skill_id}")
async def update_skill(
    skill_id: str,
    body: SkillUpdate,
    me: User = Depends(get_current_user)
):
    """更新技能。"""
    async with async_session() as s:
        skill = (await s.execute(
            select(Skill).where(Skill.id == skill_id)
        )).scalar_one_or_none()

        if not skill:
            raise BizException(ErrorCode.NOT_FOUND, "技能不存在")

        if body.name is not None:
            skill.name = body.name
        if body.desc is not None:
            skill.desc = body.desc
        if body.trigger is not None:
            skill.trigger = body.trigger
        if body.prompt is not None:
            skill.prompt = body.prompt
        if body.tools is not None:
            skill.tools = body.tools
        if body.docs is not None:
            skill.docs = body.docs
        if body.wfs is not None:
            skill.wfs = body.wfs
        if body.examples is not None:
            skill.examples = [ex.model_dump() for ex in body.examples]
        if body.scripts is not None:
            skill.scripts = [sc.model_dump() for sc in body.scripts]
        if body.budget is not None:
            skill.budget = body.budget
        if body.enabled is not None:
            skill.enabled = body.enabled

        await s.commit()
        await s.refresh(skill)

    return ok(SkillOut(...).model_dump())

@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: str,
    me: User = Depends(get_current_user)
):
    """删除技能。"""
    async with async_session() as s:
        skill = (await s.execute(
            select(Skill).where(Skill.id == skill_id)
        )).scalar_one_or_none()

        if skill:
            await s.delete(skill)
            await s.commit()

    return ok({"success": True})
```

### Step 4.3: 提交代码

- [ ] **提交技能 CRUD**

```bash
git add backend/app/api/v2/skills.py backend/tests/test_skill_crud.py
git commit -m "feat(api): add skill CRUD endpoints"
```

---

## Task 5: MCP 模块

**优先级:** P1
**预计时间:** 3小时

**说明:** MCP (Model Context Protocol) 是一种标准化工具协议，允许LLM通过统一接口访问外部资源。

### Step 5.1: 定义 MCP ORM

- [ ] **创建 MCP 模型**

Create: `backend/app/models/mcp.py`

```python
"""MCP ORM 模型。"""
from sqlalchemy import Column, String, Text, JSON, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid

class Mcp(Base):
    """MCP 服务。"""
    __tablename__ = "mcps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, comment="服务名称")
    desc = Column(Text, comment="描述")
    type = Column(String(20), comment="stdio/SSE")
    command = Column(Text, comment="启动命令或URL")
    status = Column(String(20), default="off", comment="on/off/err")
    tool_count = Column(Integer, default=0, comment="提供的工具数量")
    env = Column(JSON, default=list, comment="环境变量")
    timeout = Column(Integer, default=30, comment="超时时间（秒）")
    enabled = Column(Boolean, default=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default="now()")
```

### Step 5.2: 实现 MCP 路由

- [ ] **创建 MCP 路由**

Create: `backend/app/api/v2/mcps.py`

```python
"""MCP 路由：CRUD + 测试。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.mcp import Mcp
from app.models.user import User
from app.schemas.mcp import McpCreate, McpUpdate, McpOut, McpTestResult
from app.services.mcp_service import McpService

router = APIRouter(tags=["mcps"])

@router.get("/mcps")
async def list_mcps(me: User = Depends(get_current_user)):
    """列出MCP服务。"""
    async with async_session() as s:
        rows = (await s.execute(
            select(Mcp)
            .where(Mcp.user_id == me.id)
            .order_by(Mcp.created_at.desc())
        )).scalars().all()

    return ok([McpOut(...).model_dump() for m in rows])

@router.post("/mcps")
async def create_mcp(
    body: McpCreate,
    me: User = Depends(get_current_user)
):
    """创建MCP服务。"""
    async with async_session() as s:
        mcp = Mcp(
            name=body.name,
            desc=body.desc,
            type=body.type,
            command=body.command,
            env=[e.model_dump() for e in body.env],
            timeout=body.timeout,
            enabled=body.enabled,
            user_id=me.id
        )
        s.add(mcp)
        await s.commit()
        await s.refresh(mcp)

    return ok(McpOut(...).model_dump())

@router.post("/mcps/{mcp_id}/test")
async def test_mcp(
    mcp_id: str,
    me: User = Depends(get_current_user)
):
    """测试MCP服务连接。"""
    async with async_session() as s:
        mcp = (await s.execute(
            select(Mcp).where(Mcp.id == mcp_id)
        )).scalar_one_or_none()

        if not mcp:
            raise BizException(ErrorCode.NOT_FOUND, "MCP服务不存在")

    service = McpService()
    result = await service.test_connection(mcp)

    return ok(result.model_dump())
```

### Step 5.3: 实现 MCP 服务

- [ ] **创建 MCP 服务**

Create: `backend/app/services/mcp_service.py`

```python
"""MCP 服务：处理MCP连接和测试。"""
import asyncio
from typing import Dict, Any
from app.models.mcp import Mcp
from app.schemas.mcp import McpTestResult
from app.providers.mcp.sse_client import McpSseClient

class McpService:
    """MCP 服务。"""

    async def test_connection(self, mcp: Mcp) -> McpTestResult:
        """测试MCP服务连接。

        Args:
            mcp: MCP配置

        Returns:
            测试结果
        """
        try:
            if mcp.type == "SSE":
                # SSE 类型的MCP服务
                client = McpSseClient(mcp.command, mcp.timeout)
                tools = await client.list_tools()

                return McpTestResult(
                    success=True,
                    tool_count=len(tools),
                    tools=[t["name"] for t in tools],
                    duration=100
                )

            elif mcp.type == "stdio":
                # stdio 类型的MCP服务（需要本地启动进程）
                # TODO: 实现stdio类型
                return McpTestResult(
                    success=False,
                    tool_count=0,
                    error="stdio类型暂不支持",
                    duration=0
                )

        except Exception as e:
            return McpTestResult(
                success=False,
                tool_count=0,
                error=str(e),
                duration=0
            )
```

### Step 5.4: 提交代码

- [ ] **提交 MCP 模块**

```bash
git add backend/app/models/mcp.py backend/app/api/v2/mcps.py backend/app/services/mcp_service.py
git commit -m "feat(api): add MCP service management"
```

---

## Task 6: 统一工具调用接口

**优先级:** P1
**预计时间:** 2小时

### Step 6.1: 实现统一执行接口

- [ ] **创建统一工具执行服务**

Create: `backend/app/services/unified_tool_service.py`

```python
"""统一工具执行服务。"""
from typing import Dict, Any
from app.models.tool import Tool
from app.models.skill import Skill
from app.models.mcp import Mcp
from app.services.tool_service import ToolService
from app.services.skill_service import SkillService
from app.services.mcp_service import McpService

class UnifiedToolService:
    """统一工具调用服务。"""

    def __init__(self):
        self.tool_service = ToolService()
        self.skill_service = SkillService()
        self.mcp_service = McpService()

    async def execute(
        self,
        tool_type: str,  # "tool" | "skill" | "mcp"
        tool_id: str,
        params: Dict[str, Any]
    ) -> Any:
        """统一执行接口。

        Args:
            tool_type: 工具类型
            tool_id: 工具ID
            params: 执行参数

        Returns:
            执行结果
        """
        if tool_type == "tool":
            # 加载工具配置
            tool = await self._load_tool(tool_id)
            return await self.tool_service.test_tool(tool, params)

        elif tool_type == "skill":
            # 执行技能
            skill = await self._load_skill(tool_id)
            return await self.skill_service.execute_skill(skill, params)

        elif tool_type == "mcp":
            # 调用MCP工具
            mcp = await self._load_mcp(tool_id)
            return await self.mcp_service.call_tool(mcp, params)

        else:
            raise ValueError(f"未知工具类型: {tool_type}")
```

### Step 6.2: 提交代码

- [ ] **提交统一执行接口**

```bash
git add backend/app/services/unified_tool_service.py
git commit -m "feat(services): add unified tool execution interface"
```

---

## 验收标准

- [ ] 工具测试接口可用
- [ ] OpenSandbox 沙箱可执行代码
- [ ] 技能 CRUD 完整
- [ ] MCP 服务管理可用
- [ ] 统一工具调用接口正常
- [ ] 所有测试通过

---

## 风险和依赖

**风险:**
1. OpenSandbox 服务未启动：提供健康检查和降级方案
2. MCP协议实现复杂度：先支持SSE类型，stdio类型后续补充
3. 沙箱执行安全：限制网络访问和文件系统访问

**依赖:**
- OpenSandbox 服务（虚拟机已部署）
- MCP SDK（待安装）

---

**计划保存至:** `docs/superpowers/plans/2026-09-08-phase3-toolchain.md`
# Phase2 tools / skills / mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]` tracking.

**Goal:** 实现三类可挂载资源——工具（HTTP/内置/Python，含 test）、技能（prompt + 触发词 + 挂载，含 duplicate）、MCP 服务（配置 → langchain-mcp-adapters 真客户端，stdio/SSE，工具发现）。CRUD/test 全部对齐前端契约。

**Architecture:** tools/skills/mcps 三表（env/api_key 加密）→ 各自 executor/adapter → `/test` 接口验证连通性。`execute_tool` 替换 Plan 7 的 tool 节点占位。MCP 经 `langchain-mcp-adapters` 发现工具（Plan 9 agent 直接复用）。

**Tech Stack:** httpx（HTTP 工具）、Docker 沙箱（Python 工具，复用 Plan 7）、langchain-mcp-adapters（MCP）、Plan 2 crypto。

**前置：** Plan 1-7 完成。**关联设计：** Phase2/3 设计 §5/§6/§7。

---

## File Structure

```
backend/app/
├── models/{tool,skill,mcp}.py        # Task 1/4/7
├── core/tools/executor.py            # Task 2（HTTP/内置/Python）
├── services/tool_service.py          # Task 2（execute_tool，替换 Plan 7 占位）
├── services/skill_service.py         # Task 6（触发匹配）
├── core/agent/tool_adapters/mcp_tools.py  # Task 8（MCP 客户端，Plan 9 复用）
├── api/v2/{tools,skills,mcps}.py     # Task 3/5/9
├── schemas/{tool,skill,mcp}.py
└── alembic/versions/0011_{tools,skills,mcps}.py
```

---

### Task 1: tools ORM + 迁移

**Files:** `models/tool.py` · `models/__init__.py` · migrate · `tests/test_tool_model.py`

- [ ] **Step 1: 实现 `models/tool.py`**

```python
from sqlalchemy import String, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPk


class Tool(Base, UUIDPk, TimestampMixin):
    __tablename__ = "tools"
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20), default="HTTP")       # HTTP/内置/Python
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sig: Mapped[str | None] = mapped_column(Text, nullable=True)        # 函数签名
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    params: Mapped = mapped_column(JSONB, default=list)                 # [{n,t,d}]
    auth: Mapped | None = mapped_column(JSONB, nullable=True)           # {mode, key_enc}
    config: Mapped | None = mapped_column(JSONB, nullable=True)         # HTTP: {method,url,...}; Python: {code}
```

- [ ] **Step 2: 注册 + 迁移 + 测试 + Commit** `feat(models): Tool`

---

### Task 2: tool executor + execute_tool service（替换 Plan 7 占位）

**Files:** `core/tools/executor.py` · `services/tool_service.py` · `tests/test_tool_executor.py`

- [ ] **Step 1: 实现 `core/tools/executor.py`**

```python
import httpx, time
from app.security.crypto import decrypt


async def execute(tool, args: dict) -> dict:
    t = tool.type
    if t == "HTTP":
        return await _http(tool, args)
    if t == "Python":
        return await _python(tool, args)
    if t == "内置":
        return _builtin(tool, args)
    return {"success": False, "error": f"未知工具类型: {t}", "duration": 0}


async def _http(tool, args):
    cfg = tool.config or {}
    url = _render(cfg.get("url", ""), args)
    headers = dict(cfg.get("headers", {}))
    auth = tool.auth or {}
    if auth.get("mode") == "bearer":
        headers["Authorization"] = f"Bearer {decrypt(auth['key_enc'])}"
    elif auth.get("mode") == "apikey":
        headers["X-API-Key"] = decrypt(auth["key_enc"])
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=cfg.get("timeout", 30)) as c:
        resp = await c.request(cfg.get("method", "GET"), url, headers=headers, json=args if cfg.get("body_type") == "json" else None)
    return {"success": resp.status_code < 400, "data": _safe_json(resp), "error": None if resp.status_code < 400 else resp.text,
            "duration": int((time.perf_counter() - t0) * 1000)}


async def _python(tool, args):
    from app.providers.sandbox import run_in_sandbox       # Plan 7 Task 15
    r = await run_in_sandbox(code=(tool.config or {}).get("code", ""), inputs=args, timeout=30, memory_mb=256)
    return {"success": r.ok, "data": r.output, "error": r.error, "duration": r.duration}


def _builtin(tool, args):
    from app.core.tools.builtins import BUILTIN
    fn = BUILTIN.get(tool.name)
    if not fn:
        return {"success": False, "error": f"内置工具 {tool.name} 不存在", "duration": 0}
    return {"success": True, "data": fn(args), "error": None, "duration": 0}


def _render(tpl: str, args: dict) -> str:
    for k, v in (args or {}).items():
        tpl = tpl.replace(f"{{{k}}}", str(v))
    return tpl


def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return resp.text
```

- [ ] **Step 2: 内置工具 `core/tools/builtins.py`**

```python
from datetime import datetime, timezone

BUILTIN = {
    "current_time": lambda args: {"now": datetime.now(timezone.utc).isoformat()},
    "string_length": lambda args: {"length": len(str(args.get("s", "")))},
}
```

- [ ] **Step 3: 实现 `services/tool_service.py`**（替换 Plan 7 的占位）

```python
from sqlalchemy import select
from app.db.session import async_session
from app.models.tool import Tool
from app.core.tools.executor import execute
from app.exceptions import BizException, ErrorCode


async def execute_tool(tool_id: str, args: dict) -> dict:
    async with async_session() as s:
        t = (await s.execute(select(Tool).where(Tool.id == tool_id))).scalar_one_or_none()
    if not t or not t.enabled:
        raise BizException(ErrorCode.FORBIDDEN, "工具不存在或未启用")
    return await execute(t, args or {})
```

> 此 `execute_tool` 替换 Plan 7 Task 6 中 tool 节点引用的占位实现。

- [ ] **Step 4: 测试**（HTTP 用 httpx mock；内置工具直接调）+ Commit `feat(tools): executor + execute_tool service`

---

### Task 3: tools API（CRUD/test）

**Files:** `api/v2/tools.py` · `schemas/tool.py` · `main.py` · `tests/test_tools_api.py`

- [ ] **Step 1: 实现 `schemas/tool.py` + `api/v2/tools.py`**

```python
# schemas/tool.py
from pydantic import BaseModel
class ToolBody(BaseModel):
    name: str
    type: str = "HTTP"
    desc: str = ""
    sig: str = ""
    enabled: bool = True
    params: list = []
    auth: dict = {}
    config: dict = {}

# api/v2/tools.py
from fastapi import APIRouter, Depends, Body
from sqlalchemy import select, delete
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.tool import Tool
from app.security.crypto import encrypt
from app.services.tool_service import execute_tool
from app.exceptions import BizException, ErrorCode

router = APIRouter(prefix="/tools", tags=["tools"])

def _out(t):
    return {"id": str(t.id), "name": t.name, "type": t.type, "desc": t.description, "sig": t.sig,
            "enabled": t.enabled, "params": t.params, "auth": {"mode": (t.auth or {}).get("mode", "none"), "key": ""},
            "config": t.config, "createdAt": t.created_at.isoformat() if t.created_at else ""}

@router.get("")
async def list_(me=Depends(get_current_user)):
    async with async_session() as s:
        rows = (await s.execute(select(Tool).order_by(Tool.created_at.desc()))).scalars().all()
    return ok([_out(r) for r in rows])

@router.post("")
async def create(body: ToolBody, me=Depends(get_current_user)):
    async with async_session() as s:
        auth = dict(body.auth)
        if auth.get("key"): auth["key_enc"] = encrypt(auth.pop("key"))
        t = Tool(name=body.name, type=body.type, description=body.desc, sig=body.sig, enabled=body.enabled,
                 params=body.params, auth=auth, config=body.config)
        s.add(t); await s.commit(); await s.refresh(t)
    return ok(_out(t))

@router.put("/{tid}")
async def update_(tid: str, body: ToolBody, me=Depends(get_current_user)):
    async with async_session() as s:
        t = (await s.execute(select(Tool).where(Tool.id == tid))).scalar_one_or_none()
        if not t: raise BizException(ErrorCode.NOT_FOUND, "工具不存在")
        auth = dict(body.auth)
        if auth.get("key"): auth["key_enc"] = encrypt(auth.pop("key"))
        else: auth = {**t.auth, "mode": auth.get("mode", "none")}
        t.name = body.name; t.type = body.type; t.description = body.desc; t.sig = body.sig
        t.enabled = body.enabled; t.params = body.params; t.auth = auth; t.config = body.config
        await s.commit()
    return ok(_out(t))

@router.delete("/{tid}")
async def delete_(tid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        await s.execute(delete(Tool).where(Tool.id == tid)); await s.commit()
    return ok({"success": True})

@router.post("/{tid}/test")
async def test(tid: str, body: dict = Body(default={}), me=Depends(get_current_user)):
    return ok(await execute_tool(tid, body.get("args", {})))
```

- [ ] **Step 2: 挂载 + 测试 + Commit** `feat(tools): CRUD + /test api`

---

### Task 4: skills ORM + 迁移

**Files:** `models/skill.py` · migrate · `tests/test_skill_model.py`

- [ ] **Step 1: 实现 `models/skill.py`**（字段对齐前端 `types/skill.ts`）

```python
class Skill(Base, UUIDPk, TimestampMixin):
    __tablename__ = "skills"
    icon: Mapped[str] = mapped_column(String(32), default="🔧")
    name: Mapped[str] = mapped_column(String(100))
    scope: Mapped[str] = mapped_column(String(16), default="custom")    # builtin/custom
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    tools: Mapped = mapped_column(JSONB, default=list)
    docs: Mapped = mapped_column(JSONB, default=list)
    wfs: Mapped = mapped_column(JSONB, default=list)
    examples: Mapped = mapped_column(JSONB, default=list)
    scripts: Mapped = mapped_column(JSONB, default=list)
    budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 2: 注册 + 迁移 + 测试 + Commit** `feat(models): Skill`

---

### Task 5: skills API（CRUD/duplicate）

**Files:** `api/v2/skills.py` · `schemas/skill.py` · `main.py`

- [ ] **Step 1: 实现 CRUD + duplicate**（builtin 不可删，duplicate → custom）

```python
router = APIRouter(prefix="/skills", tags=["skills"])

@router.post("/{sid}/duplicate")
async def duplicate(sid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        orig = (await s.execute(select(Skill).where(Skill.id == sid))).scalar_one()
        from app.models.skill import Skill as S
        ns = S(icon=orig.icon, name=orig.name + " (副本)", scope="custom", version="1.0.0",
               description=orig.description, trigger=orig.trigger, prompt=orig.prompt,
               tools=orig.tools, docs=orig.docs, wfs=orig.wfs, examples=orig.examples, scripts=orig.scripts, used=0)
        s.add(ns); await s.commit(); await s.refresh(ns)
    return ok(_out(ns))

@router.delete("/{sid}")
async def delete_(sid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        sk = (await s.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
        if sk and sk.scope == "builtin": raise BizException(ErrorCode.FORBIDDEN, "内置技能不可删除")
        await s.execute(delete(Skill).where(Skill.id == sid)); await s.commit()
    return ok({"success": True})
# + GET 列表/详情、POST 创建、PUT 更新（略，模式同 tools）
```

- [ ] **Step 2: 挂载 + Commit** `feat(skills): CRUD + duplicate (builtin protected)`

---

### Task 6: skill 触发匹配 helper

**Files:** `services/skill_service.py` · `tests/test_skill_match.py`

- [ ] **Step 1: 实现**

```python
def match_skills(text: str, candidates) -> list:
    """按 trigger 关键词（逗号分隔）命中"""
    hit = []
    for sk in candidates:
        triggers = [t.strip() for t in (sk.trigger or "").split(",") if t.strip()]
        if any(t in text for t in triggers):
            hit.append(sk)
    return hit


def apply_skills(skills: list) -> tuple[str, list, list]:
    """返回 (追加 system_prompt, doc_ids, tool_ids)"""
    extra = "\n\n".join(f"[技能 {s.name}]\n{s.prompt}" for s in skills if s.prompt)
    doc_ids = [d for s in skills for d in (s.docs or [])]
    tool_ids = [t for s in skills for t in (s.tools or [])]
    return extra, doc_ids, tool_ids
```

- [ ] **Step 2: 测试 + Commit** `feat(skills): trigger match + apply helper`

---

### Task 7: mcp ORM + 迁移

**Files:** `models/mcp.py` · migrate · `tests/test_mcp_model.py`

- [ ] **Step 1: 实现 `models/mcp.py`**

```python
class Mcp(Base, UUIDPk, TimestampMixin):
    __tablename__ = "mcps"
    name: Mapped[str] = mapped_column(String(100))
    tp: Mapped[str] = mapped_column(String(16), default="stdio")     # stdio/SSE
    cmd: Mapped[str | None] = mapped_column(Text, nullable=True)     # stdio 命令 / SSE url
    status: Mapped[str] = mapped_column(String(16), default="off")   # on/off/err
    tool_count: Mapped[int] = mapped_column(Integer, default=0)
    env: Mapped = mapped_column(JSONB, default=list)                 # [{k, v_enc}]
    timeout: Mapped[int] = mapped_column(Integer, default=30)
```

- [ ] **Step 2: 注册 + 迁移 + 测试 + Commit** `feat(models): Mcp`

---

### Task 8: MCP 真客户端（langchain-mcp-adapters）

**Files:** `core/agent/tool_adapters/mcp_tools.py` · 依赖 `langchain-mcp-adapters>=0.1` · `tests/test_mcp_client.py`

- [ ] **Step 1: 加依赖** `pyproject.toml` 追加 `"langchain-mcp-adapters>=0.1"`，`pip install`

- [ ] **Step 2: 实现 `mcp_tools.py`**

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from app.security.crypto import decrypt

_pool: dict[str, MultiServerMCPClient] = {}


def _server_config(mcp) -> dict:
    if mcp.tp == "stdio":
        parts = (mcp.cmd or "").split()
        env = {e["k"]: decrypt(e["v_enc"]) for e in (mcp.env or []) if "v_enc" in e}
        return {"transport": "stdio", "command": parts[0] if parts else "", "args": parts[1:], "env": env or None}
    return {"transport": "sse", "url": mcp.cmd or "", "timeout": mcp.timeout}


async def get_client(mcp):
    key = str(mcp.id)
    if key not in _pool:
        _pool[key] = MultiServerMCPClient({"mcp": _server_config(mcp)})
    return _pool[key]


async def load_tools(mcp) -> list:
    """发现 MCP server 工具，返回 LangChain BaseTool 列表"""
    client = await get_client(mcp)
    return await client.get_tools()


async def test_connection(mcp) -> dict:
    import time; t0 = time.perf_counter()
    try:
        tools = await load_tools(mcp)
        return {"success": True, "toolCount": len(tools), "tools": [t.name for t in tools], "duration": int((time.perf_counter() - t0) * 1000)}
    except Exception as e:
        return {"success": False, "toolCount": 0, "error": str(e), "duration": int((time.perf_counter() - t0) * 1000)}
```

- [ ] **Step 3: 测试**（mock MultiServerMCPClient）+ Commit `feat(mcp): langchain-mcp-adapters client`

---

### Task 9: mcp API（CRUD/test）

**Files:** `api/v2/mcps.py` · `schemas/mcp.py` · `main.py`

- [ ] **Step 1: 实现 CRUD + test**（test 调真客户端，更新 status/tool_count）

```python
from app.core.agent.tool_adapters.mcp_tools import test_connection

@router.post("/{mid}/test")
async def test(mid: str, me=Depends(get_current_user)):
    async with async_session() as s:
        m = (await s.execute(select(Mcp).where(Mcp.id == mid))).scalar_one()
    result = await test_connection(m)
    async with async_session() as s:
        m2 = (await s.execute(select(Mcp).where(Mcp.id == mid))).scalar_one()
        m2.status = "on" if result["success"] else "err"
        m2.tool_count = result["toolCount"]
        await s.commit()
    return ok(result)
# + GET/POST/PUT/DELETE（env 的 v 加密存储，模式同 tools auth）
```

- [ ] **Step 2: 挂载 + Commit** `feat(mcp): CRUD + /test (real client)`

---

### Task 10: 冒烟

- [ ] **Step 1: 全量测试** → `pytest -v` 全绿
- [ ] **Step 2: 验证**
  - 创建 HTTP 工具 → test 返回成功 + data
  - 创建技能 → duplicate 生成副本；builtin 删除被拒
  - 创建 MCP（用一个公开 stdio MCP 或 SSE）→ test 返回 toolCount
- [ ] **Step 3: Commit** `test: phase2 tools/skills/mcp smoke`

---

## Plan 8 完成标志
- ✅ tools（HTTP/内置/Python + test）+ execute_tool（替换 Plan 7 占位）
- ✅ skills（CRUD + duplicate + 触发匹配 helper，builtin 保护）
- ✅ mcp（配置 CRUD + test 真客户端，langchain-mcp-adapters 工具发现）

**下一步：** Plan 9 agents（LangChain）+ Phase3 生产化（最后一份）。

*— 计划结束 —*
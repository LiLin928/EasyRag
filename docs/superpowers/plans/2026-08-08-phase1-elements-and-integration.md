# Phase1 elements 懒加载 + 联调收尾 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]` tracking.

**Goal:** 实现引用懒加载（`/elements/:id` 完整 DocElement + `/elements/:id/context` 上下文窗口），并完成 Phase1 前端关 mock 接真后端的端到端联调与验收——闭合"上传→解析→提问→流式回答→点击引用看原文"完整链路。

**Architecture:** 引用的 `element_id` 即 `chunk_id`（Plan 4/5 已如此）。`/elements/:id` 按 chunk 返回完整 DocElement（doc_title/node_title/page/seq/prev/next）；`/context` 返回前后 N 个兄弟 chunk。最后是联调 checklist + Phase1 验收。

**前置：** Plan 1-5 完成。

---

## File Structure

```
backend/app/api/v2/elements.py     # Task 1/2（引用懒加载）
backend/docs/phase1-integration-checklist.md   # Task 3
backend/tests/test_phase1_acceptance.py        # Task 4
```

---

### Task 1: /elements/:id 引用懒加载

**Files:** `app/api/v2/elements.py` · `main.py` · `tests/test_elements_api.py`

> 返回完整 DocElement（对齐前端 `types/knowledge.ts`）：element_id/doc_title/type/content/node_id/node_title/page_number/seq/prev_element_id/next_element_id。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_element_detail_with_prev_next():
    # 插入 3 个 chunk（seq 0,1,2），查中间那个
    ...
    r = await c.get(f"/api/v2/elements/{mid_id}", headers=H)
    d = r.json()["data"]
    assert d["element_id"] == mid_id
    assert d["prev_element_id"] and d["next_element_id"]
    assert "doc_title" in d and "content" in d
```

- [ ] **Step 2: 实现 `app/api/v2/elements.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.chunk import Chunk
from app.models.document import Document
from app.exceptions import BizException, ErrorCode

router = APIRouter(tags=["elements"])


@router.get("/elements/{chunk_id}")
async def element_detail(chunk_id: str, me=Depends(get_current_user)):
    async with async_session() as s:
        c = (await s.execute(select(Chunk).where(Chunk.id == chunk_id))).scalar_one_or_none()
        if not c:
            raise BizException(ErrorCode.NOT_FOUND, "元素不存在")
        doc = (await s.execute(select(Document).where(Document.id == c.document_id))).scalar_one_or_none()
        prev = (await s.execute(select(Chunk).where(Chunk.document_id == c.document_id, Chunk.seq < c.seq).order_by(Chunk.seq.desc()).limit(1))).scalar_one_or_none()
        nxt = (await s.execute(select(Chunk).where(Chunk.document_id == c.document_id, Chunk.seq > c.seq).order_by(Chunk.seq.asc()).limit(1))).scalar_one_or_none()
    return ok({
        "element_id": str(c.id), "doc_title": doc.name if doc else "", "type": "text",
        "content": c.content, "node_id": None, "node_title": c.clause_title,
        "page_number": c.page_number, "seq": c.seq,
        "prev_element_id": str(prev.id) if prev else None,
        "next_element_id": str(nxt.id) if nxt else None,
    })
```

- [ ] **Step 3: 挂载 + 测试通过 + Commit** `feat(elements): /elements/:id lazy load`

---

### Task 2: /elements/:id/context 上下文窗口

**Files:** 同上 · `tests/test_elements_context_api.py`

- [ ] **Step 1: 实现**

```python
@router.get("/elements/{chunk_id}/context")
async def element_context(chunk_id: str, window: int = 3, me=Depends(get_current_user)):
    async with async_session() as s:
        c = (await s.execute(select(Chunk).where(Chunk.id == chunk_id))).scalar_one_or_none()
        if not c:
            raise BizException(ErrorCode.NOT_FOUND, "元素不存在")
        before = (await s.execute(select(Chunk).where(Chunk.document_id == c.document_id, Chunk.seq < c.seq).order_by(Chunk.seq.desc()).limit(window))).scalars().all()[::-1]
        after = (await s.execute(select(Chunk).where(Chunk.document_id == c.document_id, Chunk.seq > c.seq).order_by(Chunk.seq.asc()).limit(window))).scalars().all()
    def _e(x): return {"element_id": str(x.id), "type": "text", "content": x.content, "page_number": x.page_number}
    return ok({"target": _e(c), "before": [_e(x) for x in before], "after": [_e(x) for x in after]})
```

- [ ] **Step 2: 测试**（验证 before/after 各 ≤ window）+ Commit `feat(elements): /elements/:id/context window`

---

### Task 3: Phase1 联调 Checklist

**Files:** `docs/phase1-integration-checklist.md`

- [ ] **Step 1: 创建 checklist 文档**

```markdown
# Phase1 前后端联调 Checklist

## 环境准备
- [ ] 后端：`cd deploy && docker compose up -d --build`，确认 postgres/redis/backend/worker 全部 healthy
- [ ] 后端：在 settings 页配置一个 LLM 模型（设为默认 qa）+ 一个 embedding 模型（设默认 retrieval）+ 一个 rerank 模型（可选）
- [ ] 前端：`frontend/.env.development` 设 `VITE_USE_MOCK=false`，`VITE_API_BASE=/api/v2`
- [ ] Nginx/反代：`/api/v2/*` → backend:8000（SSE 关闭 buffering，proxy_read_timeout 300s）

## 端到端用例
- [ ] 登录（admin/admin123）→ 进入主界面
- [ ] 知识库：新建 → 上传 PDF/DOCX/MD → 看到 pending → 轮询到 done（pct 100）
- [ ] 文档详情：查看结构树（嵌套章节）+ 元素列表
- [ ] 对话：选文档 → 提问 → 看到阶段指示(parse→navigate→retrieve→generate) → 流式 token → 引用卡片
- [ ] 引用：点击卡片 → 展开看原文（/elements/:id）→ "查看上下文"（/elements/:id/context）
- [ ] 多轮：追问 → 验证查询改写生效（回答结合上下文）
- [ ] 会话：左侧列表 → 切换 → 历史消息正确
- [ ] 反馈：👍/👎 可点
- [ ] 场景：切换 general/bidding → 检索参数变化
- [ ] settings：增删改模型、场景

## 契约校验
- [ ] 统一响应 `{code,message,data}`，code===0 成功
- [ ] token 过期（40101）自动 refresh
- [ ] SSE 事件名：phase/navigation/references/token/done/trace/error
```

- [ ] **Step 2: Commit** `docs: phase1 integration checklist`

---

### Task 4: Phase1 验收测试

**Files:** `tests/test_phase1_acceptance.py`

- [ ] **Step 1: 写端到端验收测试（登录→建KB→上传→轮询→对话→引用）**

```python
import pytest, io
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
@pytest.mark.integration
async def test_phase1_full_loop(tmp_path, monkeypatch):
    """完整闭环（需真实 LLM/embedding 配置；CI 中标记 integration 可跳过）"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # 1. 登录
        login = await c.post("/api/v2/auth/login", json={"username":"admin","password":"admin123"})
        assert login.json()["code"] == 0
        H = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
        # 2. 建知识库
        kb = await c.post("/api/v2/knowledge", json={"name":"验收KB","scene":"general"}, headers=H)
        kb_id = kb.json()["data"]["id"]
        # 3. 上传
        up = await c.post("/api/v2/documents/upload", headers=H,
                          files={"file": ("a.md", io.BytesIO(b"# 标题\n正文内容"), "text/markdown")},
                          data={"kbId": kb_id, "mode": "fast"})
        assert up.json()["code"] == 0
        # 4. 轮询（实际需 worker 跑完；测试中 mock 或等待）
        task_id = up.json()["data"]["task_id"]
        # ... 轮询直到 done（省略循环）
        # 5. 对话 SSE（验证事件序列）
        # 6. 引用懒加载
        # 断言关键节点
```

- [ ] **Step 2: 全量测试 + Commit** `test: phase1 acceptance e2e`

- [ ] **Step 3: Phase1 验收**

执行 `docs/phase1-integration-checklist.md` 逐项打勾。全部通过 = **Phase1 核心闭环交付**。

---

## Plan 6 完成标志
- ✅ `/elements/:id`（引用懒加载，完整 DocElement）+ `/elements/:id/context`（上下文窗口）
- ✅ Phase1 联调 checklist + 验收测试
- ✅ **Phase1 核心闭环完成**：auth + knowledge(上传/解析/树/元素) + chat(SSE 对话+引用+历史) + settings(模型/场景) 全部打通，前端关 mock 接真后端

**🟢 Phase1 全部完成（Plan 1-6）。** 下一步进入 Phase2：Plan 7 workflow（LangGraph）。

*— 计划结束 —*
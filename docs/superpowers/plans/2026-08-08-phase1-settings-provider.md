# Phase1 settings + provider + langchain_factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 settings 页可配置多 provider/多用途模型与检索场景，并暴露 LangChain 1.X 的 `build_chat_model`/`build_embeddings` 与可切换 tracing（LangSmith ↔ 自部署 Langfuse），为 chat/agent/workflow 提供 LLM 能力入口。

**Architecture:** model_configs/scenes 两张表存配置（API key 加密）→ `settings_service` 读默认模型 → `langchain_factory` 把配置桥接为 LangChain `BaseChatModel`/`Embeddings`（经 `init_chat_model`/`init_embeddings`）→ Rerank 自研 provider（LangChain 无标准抽象）→ `configure_tracing` 启动时一次性配置。所有 LLM 调用经此层，settings 切默认模型即实时生效。

**Tech Stack:** LangChain 1.X（`init_chat_model`/`init_embeddings`/LCEL），OpenAI SDK（兼容 DashScope/vLLM/SiliconFlow），LangSmith，Langfuse（自部署），cryptography(Fernet 加密)，FastAPI，SQLAlchemy 2.0 async。

**前置依赖：** Plan 1（`docs/superpowers/plans/2026-08-08-phase1-infrastructure.md`）已完成——`app.config.settings`、`app.db.session`、`app.models.base`、`app.api.response`/`app.exceptions`、`app.api.deps.get_current_user`、Alembic、`app/main.py` 均就绪。

**关联设计：** `docs/backend-plans/后端开发设计方案.md` §5.2、§4.2；`docs/backend-plans/后端设计方案-Phase2-3详细设计.md` §1.2、§1.3、§9。

---

## File Structure

```
backend/
├── pyproject.toml                      # Task 1：加 langchain/openai/cryptography/langsmith/langfuse
├── app/
│   ├── config.py                       # Task 1：加 tracing + 加密相关字段
│   ├── security/
│   │   └── crypto.py                   # Task 1：Fernet 加解密
│   ├── models/
│   │   ├── model_config.py             # Task 2
│   │   ├── scene.py                    # Task 3
│   │   └── __init__.py                 # Task 3：注册新模型（autogenerate 需要）
│   ├── services/
│   │   ├── __init__.py
│   │   └── settings_service.py         # Task 4：get_default_model + CRUD
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── langchain_factory.py        # Task 6：build_chat_model/build_embeddings
│   │   ├── trace/
│   │   │   ├── __init__.py
│   │   │   └── factory.py              # Task 7：configure_tracing
│   │   └── rerank/
│   │       ├── __init__.py
│   │       ├── base.py                 # Task 5
│   │       └── api_reranker.py         # Task 5
│   ├── api/v2/
│   │   └── settings.py                 # Task 8/9：/settings/models + /settings/scenes
│   ├── schemas/
│   │   └── settings.py                 # Task 8/9：ModelDef/Scene 请求响应
│   └── core/
│       ├── __init__.py
│       └── scenes.py                   # Task 10：内置场景预设 + SceneConfig
├── alembic/versions/
│   ├── 0002_model_configs.py           # Task 2
│   └── 0003_scenes.py                  # Task 3
└── tests/
    ├── test_crypto.py                  # Task 1
    ├── test_settings_service.py        # Task 4
    ├── test_rerank.py                  # Task 5
    ├── test_langchain_factory.py       # Task 6
    ├── test_tracing.py                 # Task 7
    ├── test_settings_api.py            # Task 8/9
    └── test_seed.py                    # Task 10
```

---

### Task 1: 依赖扩展 + 密钥加密 + config 字段

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`
- Create: `backend/app/security/crypto.py`
- Test: `backend/tests/test_crypto.py`

- [ ] **Step 1: 扩展 `backend/pyproject.toml` 依赖**

在 `[project] dependencies` 数组中追加（保留 Plan 1 已有项）：

```toml
  "langchain>=1.0",
  "langchain-core>=1.0",
  "openai>=1.30",
  "langsmith>=0.1",
  "langfuse>=3.0",
  "cryptography>=42",
  "httpx>=0.27",
```

Run: `cd backend && pip install -e ".[dev]"`
Expected: 安装成功，无冲突。

- [ ] **Step 2: 扩展 `backend/app/config.py`（追加字段，不动已有）**

在 `Settings` 类内追加：

```python
    # Tracing（可切换）
    tracing_provider: str = "none"          # langsmith | langfuse | none
    langsmith_api_key: str | None = None
    langsmith_project: str = "easyrag"
    langsmith_endpoint: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3000"

    # 默认模型（seed 用，env 可不配 → 不 seed）
    llm_default_base_url: str | None = None
    llm_default_api_key: str | None = None
    llm_qa_model: str | None = None
    llm_fast_model: str | None = None
    embedding_model: str | None = None
    embedding_dim: int = 1024
    rerank_model: str | None = None
```

- [ ] **Step 3: 写失败测试 `backend/tests/test_crypto.py`**

```python
from app.security.crypto import encrypt, decrypt

def test_roundtrip():
    t = encrypt("sk-abcdef")
    assert t != "sk-abcdef"
    assert decrypt(t) == "sk-abcdef"

def test_unique_tokens():
    assert encrypt("x") != encrypt("x")

def test_decrypt_tamper_raises():
    import pytest
    t = encrypt("secret")
    with pytest.raises(Exception):
        decrypt(t[:-4] + "AAAA")
```

- [ ] **Step 4: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_crypto.py -v`
Expected: FAIL（无模块）

- [ ] **Step 5: 实现 `backend/app/security/crypto.py`**

```python
import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from app.config import settings

_SALT = b"easyrag-model-key-v1"   # 固定盐；密钥仍由 SECRET_KEY 派生，更换 SECRET_KEY 即轮换


def _fernet() -> Fernet:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_SALT, iterations=100_000)
    key = base64.urlsafe_b64encode(kdf.derive(settings.secret_key.encode()))
    return Fernet(key)


def encrypt(plain: str) -> str:
    if plain is None:
        return None
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValueError("密文已损坏或密钥不匹配")
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_crypto.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/app/config.py backend/app/security/crypto.py backend/tests/test_crypto.py
git commit -m "feat(security): fernet encryption + tracing/default-model config + deps"
```

---

### Task 2: ModelConfig ORM + 迁移

**Files:**
- Create: `backend/app/models/model_config.py`
- Modify: `backend/app/models/__init__.py`（注册）
- Migrate: `backend/alembic/versions/0002_model_configs.py`
- Test: `backend/tests/test_model_config_model.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_model_config_model.py`**

```python
import pytest
from sqlalchemy import select
from app.db.session import async_session
from app.models.model_config import ModelConfig

@pytest.mark.asyncio
async def test_create_model_config():
    async with async_session() as s:
        m = ModelConfig(grp="llm", name="qwen-plus", prov="dashscope", use="qa",
                        url="http://x", api_key_enc="enc", params={"temp": 0.3}, is_default=True)
        s.add(m); await s.commit()
        got = (await s.execute(select(ModelConfig).where(ModelConfig.grp=="llm", ModelConfig.name=="qwen-plus"))).scalar_one()
        assert got.params["temp"] == 0.3
        assert got.is_default is True
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_model_config_model.py -v`
Expected: FAIL（无模型）

- [ ] **Step 3: 实现 `backend/app/models/model_config.py`**

```python
from sqlalchemy import String, Boolean, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPk


class ModelConfig(Base, UUIDPk, TimestampMixin):
    __tablename__ = "model_configs"
    __table_args__ = (UniqueConstraint("grp", "name", name="uq_model_grp_name"),)

    grp: Mapped[str] = mapped_column(String(16), index=True)              # llm/embed/rerank
    name: Mapped[str] = mapped_column(String(128))
    prov: Mapped[str] = mapped_column(String(32))                          # dashscope/openai/ollama/azure/vllm
    use: Mapped[str | None] = mapped_column(String(32), nullable=True)     # qa/summary/rewrite/retrieval/rerank
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 4: 在 `backend/app/models/__init__.py` 注册（autogenerate 需要）**

```python
from app.models.base import Base
from app.models.user import User
from app.models.model_config import ModelConfig

__all__ = ["Base", "User", "ModelConfig"]
```

- [ ] **Step 5: 生成并应用迁移**

Run:
```bash
cd backend && alembic revision --autogenerate -m "model_configs" && alembic upgrade head
```
Expected: 生成 `0002_*.py` 含 `create_table('model_configs', ...)` 与 `uq_model_grp_name`；`upgrade head` 成功。

- [ ] **Step 6: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_model_config_model.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/model_config.py backend/app/models/__init__.py alembic/versions backend/tests/test_model_config_model.py
git commit -m "feat(models): ModelConfig ORM + migration"
```

---

### Task 3: Scene ORM + 迁移

**Files:**
- Create: `backend/app/models/scene.py`
- Modify: `backend/app/models/__init__.py`
- Migrate: `backend/alembic/versions/0003_scenes.py`
- Test: `backend/tests/test_scene_model.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_scene_model.py`**

```python
import pytest
from sqlalchemy import select
from app.db.session import async_session
from app.models.scene import Scene

@pytest.mark.asyncio
async def test_create_scene():
    async with async_session() as s:
        sc = Scene(code="general", name="通用问答", config={"top_k": 5}, built_in=True)
        s.add(sc); await s.commit()
        got = (await s.execute(select(Scene).where(Scene.code=="general"))).scalar_one()
        assert got.config["top_k"] == 5
        assert got.built_in is True
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_scene_model.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `backend/app/models/scene.py`**

```python
from sqlalchemy import String, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPk


class Scene(Base, UUIDPk, TimestampMixin):
    __tablename__ = "scenes"
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSONB)
    built_in: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 4: 在 `backend/app/models/__init__.py` 注册**

```python
from app.models.base import Base
from app.models.user import User
from app.models.model_config import ModelConfig
from app.models.scene import Scene

__all__ = ["Base", "User", "ModelConfig", "Scene"]
```

- [ ] **Step 5: 生成并应用迁移**

Run: `cd backend && alembic revision --autogenerate -m "scenes" && alembic upgrade head`
Expected: 生成 `0003_*.py` 含 `create_table('scenes', ...)`；升级成功。

- [ ] **Step 6: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_scene_model.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/scene.py backend/app/models/__init__.py alembic/versions backend/tests/test_scene_model.py
git commit -m "feat(models): Scene ORM + migration"
```

---

### Task 4: settings_service（读默认模型 + CRUD）

**Files:**
- Create: `backend/app/services/__init__.py`（空）、`backend/app/services/settings_service.py`
- Test: `backend/tests/test_settings_service.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_settings_service.py`**

```python
import pytest
from app.services.settings_service import get_default_model, set_default_model, upsert_model
from app.models.model_config import ModelConfig

@pytest.mark.asyncio
async def test_get_default_by_use_then_group():
    # 只有一个 llm 默认（use=qa），查 rewrite 应回退到它
    await upsert_model(ModelConfig(grp="llm", name="qwen-plus", prov="dashscope", use="qa", is_default=True))
    m = await get_default_model("llm", "rewrite")
    assert m is not None and m.name == "qwen-plus"
    m2 = await get_default_model("llm", "qa")
    assert m2.name == "qwen-plus"

@pytest.mark.asyncio
async def test_set_default_is_exclusive_within_group():
    await upsert_model(ModelConfig(grp="llm", name="a", prov="openai", is_default=True))
    await upsert_model(ModelConfig(grp="llm", name="b", prov="openai", is_default=False))
    await set_default_model("llm", "b")
    a = await get_default_model("llm")
    assert a.name == "b"   # b 成为唯一默认
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_settings_service.py -v`
Expected: FAIL（无模块）

- [ ] **Step 3: 实现 `backend/app/services/settings_service.py`**

```python
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session
from app.models.model_config import ModelConfig


async def get_default_model(grp: str, use: str | None = None, db: AsyncSession | None = None) -> ModelConfig | None:
    """优先返回 (grp, use) 的默认；无则回退到 grp 的默认。"""
    async def _q(s: AsyncSession):
        if use:
            r = await s.execute(select(ModelConfig).where(
                ModelConfig.grp == grp, ModelConfig.use == use,
                ModelConfig.is_default == True, ModelConfig.enabled == True))
            m = r.scalar_one_or_none()
            if m:
                return m
        r = await s.execute(select(ModelConfig).where(
            ModelConfig.grp == grp, ModelConfig.is_default == True, ModelConfig.enabled == True))
        return r.scalar_one_or_none()

    if db:
        return await _q(db)
    async with async_session() as s:
        return await _q(s)


async def set_default_model(grp: str, name: str) -> None:
    """同组互斥：先清同组默认，再置目标。"""
    async with async_session() as s:
        await s.execute(update(ModelConfig).where(ModelConfig.grp == grp).values(is_default=False))
        await s.execute(update(ModelConfig).where(ModelConfig.grp == grp, ModelConfig.name == name).values(is_default=True))
        await s.commit()


async def upsert_model(m: ModelConfig) -> ModelConfig:
    """按 (grp,name) upsert。"""
    async with async_session() as s:
        existing = (await s.execute(select(ModelConfig).where(ModelConfig.grp == m.grp, ModelConfig.name == m.name))).scalar_one_or_none()
        if existing:
            for k in ("prov", "use", "url", "api_key_enc", "params", "is_default", "enabled"):
                v = getattr(m, k)
                if v is not None:
                    setattr(existing, k, v)
            await s.commit()
            return existing
        s.add(m)
        await s.commit()
        await s.refresh(m)
        return m
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_settings_service.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services backend/tests/test_settings_service.py
git commit -m "feat(settings): get_default_model (use-aware) + set_default + upsert"
```

---

### Task 5: Rerank provider（自研，API 调用）

**Files:**
- Create: `backend/app/providers/__init__.py`（空）、`backend/app/providers/rerank/__init__.py`（空）、`backend/app/providers/rerank/base.py`、`backend/app/providers/rerank/api_reranker.py`
- Test: `backend/tests/test_rerank.py`

> 说明：LangChain 1.X 无标准 Rerank 抽象，故自研。复用 SiliconFlow/Jina/Cohere 等 rerank HTTP API（请求体 `{model, query, documents, top_n}`，返回 `results:[{index, relevance_score}]`）。

- [ ] **Step 1: 写失败测试 `backend/tests/test_rerank.py`**

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.providers.rerank.api_reranker import ApiReranker

@pytest.mark.asyncio
async def test_rerank_maps_scores():
    r = ApiReranker(url="http://x", api_key="k", model="bge-reranker")
    fake = AsyncMock()
    fake.json = AsyncMock(return_value={"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.5}]})
    fake.raise_for_status = lambda: None
    with patch("app.providers.rerank.api_reranker.httpx.AsyncClient.post", AsyncMock(return_value=fake)):
        ranked = await r.rerank("q", ["a", "b"], top_n=2)
    assert ranked == [(1, 0.9), (0, 0.5)]   # 按 score 降序，返回 (原索引, 分数)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_rerank.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `backend/app/providers/rerank/base.py`**

```python
from abc import ABC, abstractmethod


class RerankProvider(ABC):
    @abstractmethod
    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        """返回 [(原文档索引, relevance_score), ...]，按分数降序。"""
```

- [ ] **Step 4: 实现 `backend/app/providers/rerank/api_reranker.py`**

```python
import httpx
from app.providers.rerank.base import RerankProvider


class ApiReranker(RerankProvider):
    def __init__(self, url: str, api_key: str, model: str, timeout: int = 30):
        self.url = url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"}, json={
                "model": self.model, "query": query, "documents": documents, "top_n": top_n,
            })
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results", [])
        ranked = sorted([(r["index"], float(r["relevance_score"])) for r in results], key=lambda x: x[1], reverse=True)
        return ranked[:top_n]
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_rerank.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/providers backend/tests/test_rerank.py
git commit -m "feat(rerank): api reranker provider (siliconflow/jina compatible)"
```

---

### Task 6: langchain_factory（async build_chat_model / build_embeddings）

**Files:**
- Create: `backend/app/providers/langchain_factory.py`
- Test: `backend/tests/test_langchain_factory.py`

> **设计调整**：因 `get_default_model` 走 async DB，`build_chat_model`/`build_embeddings` 为 **async**（设计文档 §1.2 的同步签名在此落地为 async，调用方 `await`）。这是 LangChain ChatModel 同步构造与异步配置读取的正确衔接方式。

- [ ] **Step 1: 写失败测试 `backend/tests/test_langchain_factory.py`**

```python
import pytest
from unittest.mock import patch
from app.providers.langchain_factory import build_chat_model, build_embeddings
from app.models.model_config import ModelConfig
from app.services.settings_service import upsert_model


@pytest.mark.asyncio
async def test_build_chat_model_uses_default(monkeypatch):
    await upsert_model(ModelConfig(grp="llm", name="qwen-plus", prov="dashscope", use="qa",
                                   url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                                   api_key_enc="enc", is_default=True, params={"temp": 0.3}))
    captured = {}
    def fake_init(model, model_provider, **kw):
        captured.update(kw); captured["model"] = model; captured["provider"] = model_provider
        class _Dummy:  # 极简桩
            pass
        return _Dummy()
    monkeypatch.setattr("app.providers.langchain_factory.init_chat_model", fake_init)
    await build_chat_model(use="qa")
    assert captured["provider"] == "openai"
    assert captured["model"] == "qwen-plus"
    assert captured["base_url"].endswith("/compatible-mode/v1")


@pytest.mark.asyncio
async def test_build_chat_model_no_default_raises():
    # 清掉默认（独立测试库默认无）
    from app.db.session import async_session
    from sqlalchemy import delete
    async with async_session() as s:
        await s.execute(delete(ModelConfig))
        await s.commit()
    with pytest.raises(Exception):
        await build_chat_model(use="qa")
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_langchain_factory.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `backend/app/providers/langchain_factory.py`**

```python
from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from app.services.settings_service import get_default_model
from app.security.crypto import decrypt
from app.exceptions import BizException, ErrorCode


async def build_chat_model(use: str = "qa", **overrides) -> BaseChatModel:
    cfg = await get_default_model("llm", use)
    if not cfg:
        raise BizException(ErrorCode.DEPENDENCY_DOWN, f"未配置默认 LLM 模型（用途 {use}），请在设置页配置")
    params = {**(cfg.params or {}), **overrides}
    common = {"model": cfg.name,
              "temperature": params.get("temp", 0.7),
              "max_tokens": int(params["max_tokens"]) if params.get("max_tokens") else None}
    common = {k: v for k, v in common.items() if v is not None}
    if cfg.prov in ("openai", "dashscope", "vllm", "siliconflow"):
        return init_chat_model(model_provider="openai", base_url=cfg.url,
                               api_key=decrypt(cfg.api_key_enc) if cfg.api_key_enc else "", **common)
    if cfg.prov == "ollama":
        return init_chat_model(model_provider="ollama", base_url=cfg.url, **common)
    if cfg.prov == "azure":
        return init_chat_model(model_provider="azure_openai", azure_endpoint=cfg.url,
                               api_key=decrypt(cfg.api_key_enc) if cfg.api_key_enc else "", **common)
    raise BizException(ErrorCode.PARAM_ERROR, f"不支持的 LLM provider: {cfg.prov}")


async def build_embeddings() -> Embeddings:
    cfg = await get_default_model("embed", "retrieval") or await get_default_model("embed")
    if not cfg:
        raise BizException(ErrorCode.DEPENDENCY_DOWN, "未配置默认 Embedding 模型，请在设置页配置")
    dim = (cfg.params or {}).get("dim")
    if cfg.prov in ("openai", "dashscope", "vllm", "siliconflow"):
        kw = dict(model_provider="openai", model=cfg.name, base_url=cfg.url,
                  api_key=decrypt(cfg.api_key_enc) if cfg.api_key_enc else "")
        if dim:
            kw["dimensions"] = int(dim)
        return init_embeddings(**kw)
    if cfg.prov == "ollama":
        return init_embeddings(model_provider="ollama", model=cfg.name, base_url=cfg.url)
    raise BizException(ErrorCode.PARAM_ERROR, f"不支持的 embedding provider: {cfg.prov}")
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_langchain_factory.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers/langchain_factory.py backend/tests/test_langchain_factory.py
git commit -m "feat(provider): async build_chat_model/build_embeddings bridging model_configs"
```

---

### Task 7: tracing factory（可切换 LangSmith / 自部署 Langfuse / none）

**Files:**
- Create: `backend/app/providers/trace/__init__.py`（空）、`backend/app/providers/trace/factory.py`
- Test: `backend/tests/test_tracing.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_tracing.py`**

```python
import os
from unittest.mock import patch
from app.providers.trace.factory import configure_tracing

def test_none_does_nothing(monkeypatch):
    monkeypatch.setattr("app.providers.trace.factory.settings.tracing_provider", "none")
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    configure_tracing()
    assert "LANGSMITH_TRACING" not in os.environ

def test_langsmith_sets_env(monkeypatch):
    monkeypatch.setattr("app.providers.trace.factory.settings.tracing_provider", "langsmith")
    monkeypatch.setattr("app.providers.trace.factory.settings.langsmith_api_key", "k")
    monkeypatch.setattr("app.providers.trace.factory.settings.langsmith_project", "p")
    configure_tracing()
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "p"

def test_langfuse_registers_callback(monkeypatch):
    monkeypatch.setattr("app.providers.trace.factory.settings.tracing_provider", "langfuse")
    with patch("app.providers.trace.factory.set_callbacks") as sc, \
         patch("app.providers.trace.factory.CallbackHandler") as cb:
        configure_tracing()
        sc.assert_called_once()
        cb.assert_called_once()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_tracing.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `backend/app/providers/trace/factory.py`**

```python
import os
from langchain_core.globals import set_callbacks
from langfuse.callback import CallbackHandler
from app.config import settings


def configure_tracing() -> None:
    """启动时一次性配置 tracing。业务代码零侵入。"""
    p = settings.tracing_provider
    if p == "langsmith":
        os.environ["LANGSMITH_TRACING"] = "true"
        if settings.langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        if settings.langsmith_endpoint:
            os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    elif p == "langfuse":
        set_callbacks([CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )])
    # none: no-op
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_tracing.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers/trace backend/tests/test_tracing.py
git commit -m "feat(trace): switchable langsmith/langfuse/none provider"
```

---

### Task 8: settings models API（对齐前端 settings.ts）

**Files:**
- Create: `backend/app/schemas/settings.py`
- Create: `backend/app/api/v2/settings.py`（本 Task 先实现 models 部分，Task 9 扩展 scenes）
- Modify: `backend/app/main.py`（include settings router）
- Test: `backend/tests/test_settings_api.py`（models 部分）

> 前端 `types/settings.ts`：`ModelDef(name/prov/use/url/key/temp/ctx/dim/def/params)`。`def` 是 Python 保留字，用 alias。响应不回传 key，只回 `has_key`。

- [ ] **Step 1: 写失败测试 `backend/tests/test_settings_api.py`（models）**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token
from app.models.user import User
from sqlalchemy import select
from app.db.session import async_session

@pytest.fixture(scope="module", autouse=True)
async def _admin():
    await ensure_admin()

async def _token(c):
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
    return create_access_token(u.id)

@pytest.mark.asyncio
async def test_create_list_set_default_delete_model():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        tok = await _token(c)
        H = {"Authorization": f"Bearer {tok}"}
        # create
        r = await c.post("/api/v2/settings/models?group=llm", json={"name":"qwen-plus","prov":"dashscope","use":"qa","url":"http://x","key":"sk-1","temp":0.3,"def":True}, headers=H)
        assert r.json()["code"] == 0
        # list
        r = await c.get("/api/v2/settings/models?group=llm", headers=H)
        data = r.json()["data"]
        assert any(m["name"]=="qwen-plus" and m["has_key"] is True for m in data)
        # set default
        r = await c.put("/api/v2/settings/models/llm/default?name=qwen-plus", headers=H)
        assert r.json()["data"]["success"] is True
        # delete
        r = await c.delete("/api/v2/settings/models?group=llm&name=qwen-plus", headers=H)
        assert r.json()["code"] == 0
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_settings_api.py -v`
Expected: FAIL（无路由）

- [ ] **Step 3: 实现 `backend/app/schemas/settings.py`**

```python
from pydantic import BaseModel, Field, ConfigDict


class ModelDef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    prov: str
    use: str | None = None
    url: str | None = None
    key: str | None = None
    temp: float | None = None
    ctx: str | None = None
    dim: str | None = None
    is_default: bool = Field(default=False, alias="def")
    params: dict = {}


class ModelOut(BaseModel):
    id: str
    grp: str
    name: str
    prov: str
    use: str | None = None
    url: str | None = None
    has_key: bool = False
    is_default: bool = False
    params: dict = {}


class SceneIn(BaseModel):
    code: str
    name: str
    description: str | None = None
    config: dict


class SceneOut(BaseModel):
    id: str
    code: str
    name: str
    description: str | None = None
    config: dict
    built_in: bool = False
```

- [ ] **Step 4: 实现 `backend/app/api/v2/settings.py`（models 部分）**

```python
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.model_config import ModelConfig
from app.security.crypto import encrypt
from app.schemas.settings import ModelDef, ModelOut
from app.services.settings_service import upsert_model, set_default_model

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/models")
async def list_models(group: str | None = None, me=Depends(get_current_user)):
    async with async_session() as s:
        q = select(ModelConfig)
        if group:
            q = q.where(ModelConfig.grp == group)
        rows = (await s.execute(q)).scalars().all()
    return ok([ModelOut(id=str(r.id), grp=r.grp, name=r.name, prov=r.prov, use=r.use,
                        url=r.url, has_key=bool(r.api_key_enc), is_default=r.is_default,
                        params=r.params).model_dump() for r in rows])


@router.post("/models")
async def create_or_update_model(group: str = Query(...), body: ModelDef = Body(...), me=Depends(get_current_user)):
    params = dict(body.params or {})
    if body.temp is not None: params["temp"] = body.temp
    if body.ctx is not None: params["ctx"] = body.ctx
    if body.dim is not None: params["dim"] = body.dim
    m = ModelConfig(grp=group, name=body.name, prov=body.prov, use=body.use, url=body.url,
                    api_key_enc=encrypt(body.key) if body.key else None,
                    params=params, is_default=body.is_default)
    saved = await upsert_model(m)
    if body.is_default:
        await set_default_model(group, body.name)
    return ok({"name": saved.name, "grp": group})


@router.put("/models/{group}/default")
async def set_default(group: str, name: str = Query(...), me=Depends(get_current_user)):
    await set_default_model(group, name)
    return ok({"success": True})


@router.delete("/models")
async def delete_model(group: str = Query(...), name: str = Query(...), me=Depends(get_current_user)):
    async with async_session() as s:
        await s.execute(delete(ModelConfig).where(ModelConfig.grp == group, ModelConfig.name == name))
        await s.commit()
    return ok({"success": True})
```

- [ ] **Step 5: 在 `backend/app/main.py` 挂载 router**

在 import 区追加 `from app.api.v2 import auth, health, settings as settings_api`，并在 `include_router` 处追加：

```python
app.include_router(settings_api.router, prefix=settings.api_prefix)
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_settings_api.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/settings.py backend/app/api/v2/settings.py backend/app/main.py backend/tests/test_settings_api.py
git commit -m "feat(settings): /settings/models CRUD (group/name/default) api"
```

---

### Task 9: settings scenes API

**Files:**
- Modify: `backend/app/api/v2/settings.py`（追加 scenes 路由）
- Modify: `backend/tests/test_settings_api.py`（追加 scenes 测试）

> 前端 `settings.ts`：GET/POST `/settings/scenes`、GET/PUT/DELETE `/settings/scenes/:id`。内置场景（built_in=true）不可删除。

- [ ] **Step 1: 追加 scenes 测试到 `backend/tests/test_settings_api.py`**

```python
@pytest.mark.asyncio
async def test_scene_crud():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        tok = await _token(c)
        H = {"Authorization": f"Bearer {tok}"}
        r = await c.post("/api/v2/settings/scenes", json={"code":"custom1","name":"自定义","config":{"top_k":7}}, headers=H)
        assert r.json()["code"] == 0
        sid = r.json()["data"]["id"]
        r = await c.put(f"/api/v2/settings/scenes/{sid}", json={"name":"改","config":{"top_k":9}}, headers=H)
        assert r.json()["data"]["name"] == "改"
        r = await c.delete(f"/api/v2/settings/scenes/{sid}", headers=H)
        assert r.json()["code"] == 0
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_settings_api.py::test_scene_crud -v`
Expected: FAIL（404，无 scenes 路由）

- [ ] **Step 3: 在 `backend/app/api/v2/settings.py` 追加 scenes 路由**

```python
from app.models.scene import Scene
from app.schemas.settings import SceneIn, SceneOut
from app.exceptions import BizException, ErrorCode


def _scene_out(s: Scene) -> dict:
    return SceneOut(id=str(s.id), code=s.code, name=s.name, description=s.description,
                    config=s.config, built_in=s.built_in).model_dump()


@router.get("/scenes")
async def list_scenes(me=Depends(get_current_user)):
    async with async_session() as s:
        rows = (await s.execute(select(Scene).order_by(Scene.created_at))).scalars().all()
    return ok([_scene_out(r) for r in rows])


@router.post("/scenes")
async def create_scene(body: SceneIn, me=Depends(get_current_user)):
    async with async_session() as s:
        if (await s.execute(select(Scene).where(Scene.code == body.code))).scalar_one_or_none():
            raise BizException(ErrorCode.PARAM_ERROR, f"场景 {body.code} 已存在")
        sc = Scene(code=body.code, name=body.name, description=body.description, config=body.config)
        s.add(sc); await s.commit(); await s.refresh(sc)
    return ok(_scene_out(sc))


@router.put("/scenes/{scene_id}")
async def update_scene(scene_id: str, body: SceneIn, me=Depends(get_current_user)):
    async with async_session() as s:
        sc = (await s.execute(select(Scene).where(Scene.id == scene_id))).scalar_one_or_none()
        if not sc: raise BizException(ErrorCode.NOT_FOUND, "场景不存在")
        sc.name = body.name; sc.description = body.description; sc.config = body.config
        await s.commit(); await s.refresh(sc)
    return ok(_scene_out(sc))


@router.delete("/scenes/{scene_id}")
async def delete_scene(scene_id: str, me=Depends(get_current_user)):
    async with async_session() as s:
        sc = (await s.execute(select(Scene).where(Scene.id == scene_id))).scalar_one_or_none()
        if not sc: raise BizException(ErrorCode.NOT_FOUND, "场景不存在")
        if sc.built_in: raise BizException(ErrorCode.FORBIDDEN, "内置场景不可删除")
        await s.delete(sc); await s.commit()
    return ok({"success": True})
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_settings_api.py -v`
Expected: models + scenes 全 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v2/settings.py backend/tests/test_settings_api.py
git commit -m "feat(settings): /settings/scenes CRUD (builtin protected)"
```

---

### Task 10: 内置场景预设 + seed（默认模型 + 内置场景）

**Files:**
- Create: `backend/app/core/__init__.py`（空）、`backend/app/core/scenes.py`
- Create: `backend/app/core/seed.py`
- Modify: `backend/app/main.py`（lifespan 调 seed）
- Test: `backend/tests/test_seed.py`

- [ ] **Step 1: 实现 `backend/app/core/scenes.py`（SceneConfig + 内置预设 + get_scene_config）**

```python
from dataclasses import dataclass, asdict
from sqlalchemy import select
from app.db.session import async_session
from app.models.scene import Scene


@dataclass
class SceneConfig:
    code: str
    name: str
    description: str = ""
    system_prompt: str = ""
    chunk_size: int = 512
    top_k: int = 5
    vector_top_k: int = 20
    trgm_top_k: int = 20
    vector_weight: float = 0.7
    keyword_weight: float = 0.3
    rrf_k: int = 60
    rerank_enabled: bool = True
    rerank_threshold: float = 0.02
    rerank_top_n: int = 10
    navigation_enabled: bool = True
    nav_confidence_threshold: float = 0.15


_SYS_GENERAL = "你是专业文档问答助手。仅基于参考资料回答，用 [n] 标注引用，资料不足时明确告知。"
_SYS_BIDDING = "你是标书分析助手。重点关注表格/条款/资质，引用具体条款编号与页码，金额日期原文引用，对比以表格呈现。"

BUILTIN_SCENES = {
    "general":  {"name": "通用问答", "description": "适用于任意文档的通用检索问答", "config": {"system_prompt": _SYS_GENERAL, "chunk_size": 512, "top_k": 5, "rerank_threshold": 0.02}},
    "bidding":  {"name": "标书文档", "description": "招标/投标文件，强化表格与条款", "config": {"system_prompt": _SYS_BIDDING, "chunk_size": 768, "top_k": 8, "rerank_threshold": 0.03, "vector_weight": 0.6, "keyword_weight": 0.4}},
    "contract": {"name": "合同文档", "description": "合同条款检索", "config": {"system_prompt": _SYS_GENERAL, "chunk_size": 640, "top_k": 6}},
    "tech":     {"name": "技术文档", "description": "技术规范/手册", "config": {"system_prompt": _SYS_GENERAL, "chunk_size": 600, "top_k": 6}},
    "product":  {"name": "产品文档", "description": "产品说明/手册", "config": {"system_prompt": _SYS_GENERAL, "chunk_size": 512, "top_k": 5}},
}


def _from_dict(code: str, d: dict) -> SceneConfig:
    valid = {k: v for k, v in d.items() if k in SceneConfig.__dataclass_fields__}
    return SceneConfig(code=code, **valid)


async def get_scene_config(code: str | None) -> SceneConfig:
    code = code or "general"
    async with async_session() as s:
        sc = (await s.execute(select(Scene).where(Scene.code == code))).scalar_one_or_none()
        if sc:
            d = {"name": sc.name, "description": sc.description or "", **(sc.config or {})}
            return _from_dict(code, d)
    if code in BUILTIN_SCENES:
        b = BUILTIN_SCENES[code]
        return _from_dict(code, {"name": b["name"], "description": b["description"], **b["config"]})
    return _from_dict("general", {"name": "通用问答", **BUILTIN_SCENES["general"]["config"]})
```

- [ ] **Step 2: 实现 `backend/app/core/seed.py`**

```python
from sqlalchemy import select
from app.db.session import async_session
from app.models.scene import Scene
from app.models.model_config import ModelConfig
from app.security.crypto import encrypt
from app.core.scenes import BUILTIN_SCENES
from app.config import settings


async def seed_builtin_scenes() -> None:
    async with async_session() as s:
        for code, b in BUILTIN_SCENES.items():
            exists = (await s.execute(select(Scene).where(Scene.code == code))).scalar_one_or_none()
            if not exists:
                s.add(Scene(code=code, name=b["name"], description=b["description"], config=b["config"], built_in=True))
        await s.commit()


async def seed_default_model_from_env() -> None:
    """若 env 配了默认 LLM，且库中尚无默认 llm，则 seed 一个（开箱即用）。"""
    if not (settings.llm_default_base_url and settings.llm_default_api_key and settings.llm_qa_model):
        return
    async with async_session() as s:
        has = (await s.execute(select(ModelConfig).where(ModelConfig.grp == "llm", ModelConfig.is_default == True))).scalar_one_or_none()
        if has:
            return
        m = ModelConfig(grp="llm", name=settings.llm_qa_model, prov="dashscope", use="qa",
                        url=settings.llm_default_base_url, api_key_enc=encrypt(settings.llm_default_api_key),
                        params={"temp": 0.3}, is_default=True, enabled=True)
        s.add(m)
        await s.commit()


async def run_seed() -> None:
    await seed_builtin_scenes()
    await seed_default_model_from_env()
```

- [ ] **Step 3: 写失败测试 `backend/tests/test_seed.py`**

```python
import pytest
from sqlalchemy import select
from app.db.session import async_session
from app.models.scene import Scene
from app.core.scenes import BUILTIN_SCENES
from app.core.seed import seed_builtin_scenes

@pytest.mark.asyncio
async def test_seed_idempotent():
    await seed_builtin_scenes()
    await seed_builtin_scenes()
    async with async_session() as s:
        for code in BUILTIN_SCENES:
            rows = (await s.execute(select(Scene).where(Scene.code == code))).scalars().all()
            assert len(rows) == 1
            assert rows[0].built_in is True
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_seed.py -v`
Expected: PASS

- [ ] **Step 5: 修改 `backend/app/main.py` 的 lifespan 调 seed 与 tracing**

在 `lifespan` 内的 `await ensure_admin()` 后追加：

```python
    from app.core.seed import run_seed
    from app.providers.trace.factory import configure_tracing
    await run_seed()
    configure_tracing()
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/core backend/tests/test_seed.py backend/app/main.py
git commit -m "feat(seed): builtin scenes + env default model + tracing on startup"
```

---

### Task 11: 冒烟（配置模型 → build_chat_model 构造成功）

**Files:**
- 无新增，运行集成验证

- [ ] **Step 1: 运行全量测试**

Run: `cd backend && pytest -v`
Expected: 全绿（Plan 1 + Plan 2 所有测试 passed）。

- [ ] **Step 2: Docker 重启并验证 seed 与 settings API**

Run:
```bash
cd deploy && docker compose up -d --build
sleep 10
TOKEN=$(curl -s -X POST http://localhost:8000/api/v2/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
# 配置一个 LLM 模型（需替换为真实可用的 base_url/key/model）
curl -s -X POST "http://localhost:8000/api/v2/settings/models?group=llm" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"qwen-plus","prov":"dashscope","use":"qa","url":"https://dashscope.aliyuncs.com/compatible-mode/v1","key":"sk-xxx","temp":0.3,"def":true}'
# 查询场景
curl -s "http://localhost:8000/api/v2/settings/scenes" -H "Authorization: Bearer $TOKEN"
```
Expected:
- POST models 返回 `{"code":0,...,"data":{"name":"qwen-plus","grp":"llm"}}`
- GET scenes 返回 5 个内置场景（general/bidding/contract/tech/product），均 `built_in:true`

- [ ] **Step 3: 验证 build_chat_model 能构造（Python 交互）**

Run:
```bash
docker compose exec backend python -c "
import asyncio
from app.providers.langchain_factory import build_chat_model
m = asyncio.run(build_chat_model(use='qa'))
print('OK', type(m).__name__, getattr(m,'model_name',None))
"
```
Expected: 输出 `OK <ChatModel类名> qwen-plus`（证明配置→LangChain 桥接打通）。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: phase1 settings/provider smoke (model config → langchain bridge)"
```

---

## Plan 2 完成标志

- ✅ model_configs / scenes 两表 + 迁移；API key Fernet 加密存储
- ✅ `/settings/models`（GET/POST/PUT default/DELETE）+ `/settings/scenes`（CRUD，内置保护）可用
- ✅ `await build_chat_model(use)` / `await build_embeddings()` 把 settings 配置桥接为 LangChain 模型
- ✅ `configure_tracing()` 启动注入，`TRACING_PROVIDER` 切换 LangSmith / 自部署 Langfuse / none
- ✅ 启动 seed：5 个内置场景 +（env 配了则）默认 LLM 模型
- ✅ ApiReranker（SiliconFlow/Jina 兼容）就绪，供 Plan 4 检索管线调用

**下一步**：Plan 3（知识库 + 文档解析管线）—— 让 settings 配的 embedding 模型真正用于文档向量化。

---

*— 计划结束 —*

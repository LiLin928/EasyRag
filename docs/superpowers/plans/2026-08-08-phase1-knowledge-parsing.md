# Phase1 知识库 + 文档解析管线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现知识库 CRUD、文档上传（multipart）、异步解析管线（PDF/DOCX/XLSX/MD/TXT → 元素 → 结构化分块 → 结构树 → 批量向量化），前端可上传文档、轮询解析进度、查看结构树与元素。

**Architecture:** knowledge/documents/parse_tasks/chunks/doc_tree_nodes/element_positions 六张表 → multipart 上传存文件（Storage 抽象，本地 FS）+ 建 pending 记录 → ARQ worker 异步执行 `parse_document_task`（ParserDispatcher 按扩展名分发 → Chunker 分块 → TreeBuilder 建树 → 批量 embedding 入库）→ 前端轮询 `GET /parse-tasks/:id` 取进度。

**Tech Stack:** ARQ + Redis（异步任务），PyMuPDF/pdfplumber（PDF 文本+表格），python-docx（DOCX），openpyxl（XLSX），python-multipart（上传），SQLAlchemy 2.0 async，pgvector（向量列），Plan 2 的 `build_embeddings`。

**前置依赖：** Plan 1（基础设施）、Plan 2（settings/provider/build_embeddings）已完成。

**关联设计：** 主方案 §4.2、§5.3-5.6；Phase2/3 设计 §2.3 HybridRetriever 依赖此处产出的 chunks 表。

**设计调整**：解析用 PyMuPDF+pdfplumber+python-docx+openpyxl（轻量），**不引入 unstructured**（其依赖链过重）；向量列固定 `vector(1024)`（与 `EMBEDDING_DIM` 默认对齐，改维度需重建 chunks/doc_tree_nodes 表）。

---

## File Structure

```
backend/
├── pyproject.toml                      # Task 1：加 arq/redis/解析库/multipart
├── app/
│   ├── config.py                       # Task 5：加 STORAGE_* 字段
│   ├── models/
│   │   ├── knowledge_base.py           # Task 1
│   │   ├── document.py                 # Task 2（Document + ParseTask）
│   │   ├── chunk.py                    # Task 3
│   │   ├── tree_node.py                # Task 4（TreeNode + ElementPosition）
│   │   └── __init__.py                 # 逐 Task 注册
│   ├── providers/
│   │   └── storage/
│   │       ├── __init__.py
│   │       ├── base.py                 # Task 5
│   │       ├── local_fs.py             # Task 5
│   │       └── factory.py              # Task 5
│   ├── db/redis.py                     # Task 6
│   ├── worker/
│   │   ├── __init__.py
│   │   └── app.py                      # Task 6（WorkerSettings）
│   ├── core/parser/
│   │   ├── __init__.py
│   │   ├── models.py                   # Task 8：ParsedElement
│   │   ├── dispatcher.py               # Task 8
│   │   ├── pdf_parser.py docx_parser.py xlsx_parser.py md_parser.py  # Task 8
│   │   ├── chunker.py                  # 下回合 Task 9
│   │   └── tree_builder.py             # 下回合 Task 10
│   ├── services/knowledge_service.py   # Task 7
│   └── api/v2/
│       ├── knowledge.py                # Task 7
│       ├── documents.py                # 下回合 Task 12
│       └── parse_tasks.py              # 下回合 Task 13
├── alembic/versions/0004_knowledge.py  # Task 1
├── alembic/versions/0005_documents.py  # Task 2
├── alembic/versions/0006_chunks.py     # Task 3
├── alembic/versions/0007_tree_elements.py  # Task 4
└── tests/
    └── （各 Task 对应测试）
```

---

### Task 1: 依赖 + KnowledgeBase ORM + 迁移

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/models/knowledge_base.py`
- Modify: `backend/app/models/__init__.py`
- Migrate: `backend/alembic/versions/0004_knowledge.py`
- Test: `backend/tests/test_kb_model.py`

- [ ] **Step 1: 扩展 `backend/pyproject.toml`**

在 `dependencies` 追加：

```toml
  "arq>=0.26",
  "redis>=5.0",
  "pymupdf>=1.24",
  "pdfplumber>=0.11",
  "python-docx>=1.1",
  "openpyxl>=3.1",
  "python-multipart>=0.0.9",
```

Run: `cd backend && pip install -e ".[dev]"`

- [ ] **Step 2: 写失败测试 `backend/tests/test_kb_model.py`**

```python
import pytest
from sqlalchemy import select
from app.db.session import async_session
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User

@pytest.mark.asyncio
async def test_create_kb():
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
        kb = KnowledgeBase(user_id=u.id, name="KB1", scene="general")
        s.add(kb); await s.commit()
        assert kb.id is not None
        assert kb.chunk_size == 512
        assert kb.doc_count == 0
```

- [ ] **Step 3: 实现 `backend/app/models/knowledge_base.py`**

```python
from sqlalchemy import String, Text, Integer, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPk


class KnowledgeBase(Base, UUIDPk, TimestampMixin):
    __tablename__ = "knowledge_bases"
    user_id: Mapped = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene: Mapped[str] = mapped_column(String(32), default="general")
    cover: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chunk_size: Mapped[int] = mapped_column(Integer, default=512)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=64)
    retrieval_top_k: Mapped[int] = mapped_column(Integer, default=5)
    doc_count: Mapped[int] = mapped_column(Integer, default=0)
    total_size: Mapped[int] = mapped_column(BigInteger, default=0)
```

- [ ] **Step 4: 注册到 `backend/app/models/__init__.py`**（追加 KnowledgeBase）

```python
from app.models.knowledge_base import KnowledgeBase
__all__ = ["Base", "User", "ModelConfig", "Scene", "KnowledgeBase"]
```

- [ ] **Step 5: 生成并应用迁移**

Run: `cd backend && alembic revision --autogenerate -m "knowledge_bases" && alembic upgrade head`
Expected: `0004_knowledge.py` 含 `create_table('knowledge_bases')`，升级成功。

- [ ] **Step 6: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_kb_model.py -v` → PASS

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/app/models/knowledge_base.py backend/app/models/__init__.py alembic/versions/0004* backend/tests/test_kb_model.py
git commit -m "feat(models): KnowledgeBase + deps (arq/redis/parsers)"
```

---

### Task 2: Document + ParseTask ORM + 迁移

**Files:**
- Create: `backend/app/models/document.py`（Document + ParseTask）
- Modify: `backend/app/models/__init__.py`
- Migrate: `backend/alembic/versions/0005_documents.py`
- Test: `backend/tests/test_document_model.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_document_model.py`**

```python
import pytest
from sqlalchemy import select
from app.db.session import async_session
from app.models.document import Document, ParseTask
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User

@pytest.mark.asyncio
async def test_create_doc_and_task():
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
        kb = (await s.execute(select(KnowledgeBase))).scalars().first()
        d = Document(kb_id=kb.id, user_id=u.id, name="a.pdf", ext="pdf", size=1024,
                     mode="fast", status="pending", file_key="k/a.pdf")
        s.add(d); await s.commit()
        t = ParseTask(doc_id=d.id, kb_id=kb.id, status="pending", pct=0)
        s.add(t); await s.commit()
        assert d.status == "pending"
        assert t.doc_id == d.id
```

- [ ] **Step 2: 运行测试，确认失败** → `cd backend && pytest tests/test_document_model.py -v`（FAIL）

- [ ] **Step 3: 实现 `backend/app/models/document.py`**

```python
from sqlalchemy import String, Text, Integer, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPk


class Document(Base, UUIDPk, TimestampMixin):
    __tablename__ = "documents"
    kb_id: Mapped = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    ext: Mapped[str] = mapped_column(String(16))
    size: Mapped[int] = mapped_column(BigInteger)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[str] = mapped_column(String(16), default="fast")        # fast/precision
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending/parsing/done/failed
    pct: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_key: Mapped[str] = mapped_column(String(512))
    element_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)


class ParseTask(Base, UUIDPk, TimestampMixin):
    __tablename__ = "parse_tasks"
    doc_id: Mapped = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    kb_id: Mapped = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16), default="pending")   # pending/parsing/done/failed
    pct: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: 注册到 `__init__.py`**（追加 Document, ParseTask）

- [ ] **Step 5: 迁移** → `cd backend && alembic revision --autogenerate -m "documents and parse_tasks" && alembic upgrade head`

- [ ] **Step 6: 测试通过** → `pytest tests/test_document_model.py -v` PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/document.py backend/app/models/__init__.py alembic/versions/0005* backend/tests/test_document_model.py
git commit -m "feat(models): Document + ParseTask ORM"
```

---

### Task 3: Chunk ORM + 迁移（含向量/全文索引）

**Files:**
- Create: `backend/app/models/chunk.py`
- Modify: `backend/app/models/__init__.py`
- Migrate: `backend/alembic/versions/0006_chunks.py`
- Test: `backend/tests/test_chunk_model.py`

> 向量列固定 `vector(1024)`；ivfflat 索引需在迁移 SQL 里手写（autogenerate 不识别 pgvector 索引）。

- [ ] **Step 1: 写失败测试 `backend/tests/test_chunk_model.py`**

```python
import pytest
from sqlalchemy import select, text
from app.db.session import async_session, engine
from app.models.chunk import Chunk
from app.models.document import Document

@pytest.mark.asyncio
async def test_create_chunk_without_embedding():
    async with async_session() as s:
        d = (await s.execute(select(Document))).scalars().first()
        c = Chunk(document_id=d.id, kb_id=d.kb_id, content="hello", content_search="hello", page_number=1, seq=0)
        s.add(c); await s.commit()
        assert c.id is not None
        assert c.embedding is None   # 未向量化前为空
```

- [ ] **Step 2: 实现 `backend/app/models/chunk.py`**

```python
from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.models.base import Base, TimestampMixin, UUIDPk

EMBEDDING_DIM = 1024   # 与 config.embedding_dim 对齐；改维度需重建本表


class Chunk(Base, UUIDPk, TimestampMixin):
    __tablename__ = "chunks"
    document_id: Mapped = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    kb_id: Mapped = mapped_column(String(36), index=True)
    clause_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    content_search: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    element_count: Mapped[int] = mapped_column(Integer, default=0)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped | None = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

- [ ] **Step 3: 注册到 `__init__.py`**（追加 Chunk；需 `pip install pgvector` 已在 Plan 1 依赖）

- [ ] **Step 4: 生成迁移，再手写补索引**

Run: `cd backend && alembic revision --autogenerate -m "chunks"`（生成表结构后**不要直接 upgrade**）

打开生成的 `0006_chunks.py`，在 `upgrade()` 的 `create_table` 之后追加：

```python
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunk_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunk_trgm ON chunks USING gin (content_search gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunk_doc_page ON chunks (document_id, page_number)")
```

`downgrade()` 对应 `op.execute("DROP INDEX IF EXISTS ...")`。

- [ ] **Step 5: 应用迁移** → `cd backend && alembic upgrade head`

- [ ] **Step 6: 验证索引存在**

Run:
```bash
docker compose exec postgres psql -U easyrag -d easyrag -c "\di chunks" | grep -E "ivfflat|trgm"
```
Expected: 含 `idx_chunk_embedding`（ivfflat）与 `idx_chunk_trgm`（gin）。

- [ ] **Step 7: 测试通过** → `pytest tests/test_chunk_model.py -v` PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/chunk.py backend/app/models/__init__.py alembic/versions/0006* backend/tests/test_chunk_model.py
git commit -m "feat(models): Chunk ORM + ivfflat/pg_trgm indexes"
```

---

### Task 4: TreeNode + ElementPosition ORM + 迁移

**Files:**
- Create: `backend/app/models/tree_node.py`（TreeNode + ElementPosition）
- Modify: `backend/app/models/__init__.py`
- Migrate: `backend/alembic/versions/0007_tree_elements.py`
- Test: `backend/tests/test_tree_element_model.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_tree_element_model.py`**

```python
import pytest
from sqlalchemy import select
from app.db.session import async_session
from app.models.tree_node import TreeNode, ElementPosition
from app.models.document import Document

@pytest.mark.asyncio
async def test_create_tree_and_element():
    async with async_session() as s:
        d = (await s.execute(select(Document))).scalars().first()
        n = TreeNode(document_id=d.id, level=0, sort_order=0, title="第一章", page_start=1, page_end=5)
        s.add(n); await s.commit()
        e = ElementPosition(document_id=d.id, tree_node_id=n.id, element_type="text",
                            element_index=0, page_number=1, content="正文")
        s.add(e); await s.commit()
        assert n.id and e.id
```

- [ ] **Step 2: 实现 `backend/app/models/tree_node.py`**

```python
from sqlalchemy import String, Text, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.models.base import Base, TimestampMixin, UUIDPk

EMBEDDING_DIM = 1024


class TreeNode(Base, UUIDPk, TimestampMixin):
    __tablename__ = "doc_tree_nodes"
    document_id: Mapped = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped | None = mapped_column(ForeignKey("doc_tree_nodes.id", ondelete="CASCADE"), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    element_count: Mapped[int] = mapped_column(Integer, default=0)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nav_embedding: Mapped | None = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


class ElementPosition(Base, UUIDPk, TimestampMixin):
    __tablename__ = "element_positions"
    document_id: Mapped = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped | None = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True, index=True)
    tree_node_id: Mapped | None = mapped_column(ForeignKey("doc_tree_nodes.id", ondelete="SET NULL"), nullable=True, index=True)
    element_type: Mapped[str] = mapped_column(String(20))     # text/table/image/heading
    element_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
```

- [ ] **Step 3: 注册到 `__init__.py`**（追加 TreeNode, ElementPosition）

- [ ] **Step 4: 生成迁移并补 nav_embedding 索引**

Run: `cd backend && alembic revision --autogenerate -m "tree nodes and elements"`
在生成的 `0007_*.py` 的 `upgrade()` 追加：

```python
    op.execute("CREATE INDEX IF NOT EXISTS idx_tree_parent ON doc_tree_nodes (parent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tree_nav ON doc_tree_nodes USING ivfflat (nav_embedding vector_cosine_ops) WITH (lists = 50)")
```

- [ ] **Step 5: 应用** → `alembic upgrade head`

- [ ] **Step 6: 测试通过** → `pytest tests/test_tree_element_model.py -v` PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/tree_node.py backend/app/models/__init__.py alembic/versions/0007* backend/tests/test_tree_element_model.py
git commit -m "feat(models): TreeNode + ElementPosition ORM + nav index"
```

---

### Task 5: Storage 抽象（本地 FS 实现 + factory）

**Files:**
- Modify: `backend/app/config.py`（加 STORAGE_*）
- Create: `backend/app/providers/storage/__init__.py`、`base.py`、`local_fs.py`、`factory.py`
- Test: `backend/tests/test_storage.py`

- [ ] **Step 1: 扩展 `backend/app/config.py`**

```python
    storage_type: str = "local"        # local | minio
    storage_local_dir: str = "./data/files"
```

- [ ] **Step 2: 写失败测试 `backend/tests/test_storage.py`**

```python
import pytest, os
from app.providers.storage.factory import get_storage

@pytest.mark.asyncio
async def test_put_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.storage_local_dir", str(tmp_path))
    st = get_storage()
    key = "kb1/doc1/a.pdf"
    await st.put(key, b"hello-bytes")
    data = await st.get(key)
    assert data == b"hello-bytes"
    assert os.path.exists(os.path.join(str(tmp_path), key))
```

- [ ] **Step 3: 实现 `backend/app/providers/storage/base.py`**

```python
from abc import ABC, abstractmethod


class ObjectStorage(ABC):
    @abstractmethod
    async def put(self, key: str, data: bytes) -> None: ...
    @abstractmethod
    async def get(self, key: str) -> bytes: ...
    @abstractmethod
    async def delete(self, key: str) -> None: ...
    @abstractmethod
    async def presigned_url(self, key: str, expires: int = 3600) -> str: ...
```

- [ ] **Step 4: 实现 `backend/app/providers/storage/local_fs.py`**

```python
import os
import aiofiles
import urllib.parse
from app.providers.storage.base import ObjectStorage
from app.config import settings


class LocalFSStorage(ObjectStorage):
    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self.root, key)

    async def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)

    async def get(self, key: str) -> bytes:
        async with aiofiles.open(self._path(key), "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)

    async def presigned_url(self, key: str, expires: int = 3600) -> str:
        # 本地 FS：返回 /files/<key> 静态路由（由 Nginx 或 FastAPI StaticFiles 提供）
        return "/files/" + urllib.parse.quote(key)
```

> 需加依赖 `aiofiles`：在 `pyproject.toml` 追加 `"aiofiles>=23.2"`，`pip install -e ".[dev]"`。

- [ ] **Step 5: 实现 `backend/app/providers/storage/factory.py`**

```python
from app.config import settings
from app.providers.storage.base import ObjectStorage


def get_storage() -> ObjectStorage:
    if settings.storage_type == "minio":
        from app.providers.storage.minio_impl import MinioStorage   # Phase3 实现
        return MinioStorage()
    from app.providers.storage.local_fs import LocalFSStorage
    return LocalFSStorage(settings.storage_local_dir)
```

- [ ] **Step 6: 测试通过** → `cd backend && pytest tests/test_storage.py -v` PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/app/providers/storage backend/pyproject.toml backend/tests/test_storage.py
git commit -m "feat(storage): object storage abstraction + local fs impl"
```

---

### Task 6: ARQ worker 基础 + Redis 连接

**Files:**
- Create: `backend/app/db/redis.py`
- Create: `backend/app/worker/__init__.py`（空）、`backend/app/worker/app.py`
- Modify: `deploy/docker-compose.yml`（加 worker 服务）
- Test: `backend/tests/test_redis.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_redis.py`**

```python
import pytest
from app.db.redis import get_redis

@pytest.mark.asyncio
async def test_redis_ping():
    r = await get_redis()
    assert await r.ping() is True
```

- [ ] **Step 2: 实现 `backend/app/db/redis.py`**

```python
from redis.asyncio import Redis
from app.config import settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis
```

- [ ] **Step 3: 测试通过**（需 compose redis 已起） → `pytest tests/test_redis.py -v` PASS

- [ ] **Step 4: 实现 `backend/app/worker/app.py`（先空函数注册表，parse_document_task 在 Task 12 实现）**

```python
from arq.connections import RedisSettings
from app.config import settings

async def startup(ctx):
    ctx["ok"] = True

# parse_document_task 将在 Task 12 追加到此文件并加入 functions
class WorkerSettings:
    functions = []                      # Task 12 追加 parse_document_task
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    max_jobs = 4
    job_timeout = 600
    max_tries = 3
```

- [ ] **Step 5: 在 `deploy/docker-compose.yml` 追加 worker 服务**

```yaml
  worker:
    build: ../backend
    env_file: ../backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://easyrag:easyrag@postgres:5432/easyrag
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_started }
    command: arq app.worker.WorkerSettings
```

- [ ] **Step 6: 验证 worker 可启动（空函数表也能起）**

Run: `cd deploy && docker compose up -d --build worker && sleep 5 && docker compose logs worker | tail -5`
Expected: 日志含 `Starting worker`，无崩溃。

- [ ] **Step 7: Commit**

```bash
git add backend/app/db/redis.py backend/app/worker deploy/docker-compose.yml backend/tests/test_redis.py
git commit -m "feat(worker): arq worker scaffold + redis connection"
```

---

### Task 7: knowledge API CRUD（/knowledge）

**Files:**
- Create: `backend/app/services/knowledge_service.py`
- Create: `backend/app/schemas/knowledge.py`
- Create: `backend/app/api/v2/knowledge.py`
- Modify: `backend/app/main.py`（挂载）
- Test: `backend/tests/test_knowledge_api.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_knowledge_api.py`**

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
async def _admin(): await ensure_admin()

async def _token():
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
    return create_access_token(u.id)

@pytest.mark.asyncio
async def test_kb_crud():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        tok = await _token(); H = {"Authorization": f"Bearer {tok}"}
        r = await c.post("/api/v2/knowledge", json={"name":"KB1","scene":"general"}, headers=H)
        assert r.json()["code"] == 0
        kb_id = r.json()["data"]["id"]
        r = await c.get("/api/v2/knowledge", headers=H)
        assert any(k["id"]==kb_id for k in r.json()["data"])
        r = await c.put(f"/api/v2/knowledge/{kb_id}", json={"name":"KB1改"}, headers=H)
        assert r.json()["data"]["name"] == "KB1改"
        r = await c.delete(f"/api/v2/knowledge/{kb_id}", headers=H)
        assert r.json()["code"] == 0
```

- [ ] **Step 2: 实现 `backend/app/schemas/knowledge.py`**

```python
from pydantic import BaseModel

class KBCreate(BaseModel):
    name: str
    description: str | None = None
    scene: str = "general"
    cover: str | None = None

class KBUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    scene: str | None = None
    cover: str | None = None

class KBOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    scene: str
    cover: str | None = None
    doc_count: int = 0
    total_size: int = 0
    created_at: str
```

- [ ] **Step 3: 实现 `backend/app/services/knowledge_service.py`**

```python
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session
from app.models.knowledge_base import KnowledgeBase
from app.models.document import Document


async def list_kbs(user_id: str):
    async with async_session() as s:
        rows = (await s.execute(select(KnowledgeBase).where(KnowledgeBase.user_id == user_id).order_by(KnowledgeBase.created_at.desc()))).scalars().all()
        return rows

async def create_kb(user_id: str, name, description, scene, cover):
    async with async_session() as s:
        kb = KnowledgeBase(user_id=user_id, name=name, description=description, scene=scene, cover=cover)
        s.add(kb); await s.commit(); await s.refresh(kb)
        return kb

async def update_kb(kb_id: str, **fields):
    async with async_session() as s:
        await s.execute(update(KnowledgeBase).where(KnowledgeBase.id == kb_id).values(**{k:v for k,v in fields.items() if v is not None}))
        await s.commit()
        return (await s.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))).scalar_one()

async def delete_kb(kb_id: str):
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.id == kb_id))
        await s.commit()
```

- [ ] **Step 4: 实现 `backend/app/api/v2/knowledge.py`**

```python
from fastapi import APIRouter, Depends, Body
from app.api.deps import get_current_user
from app.api.response import ok
from app.schemas.knowledge import KBCreate, KBUpdate, KBOut
from app.services import knowledge_service as ks

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _out(kb) -> dict:
    return KBOut(id=str(kb.id), name=kb.name, description=kb.description, scene=kb.scene,
                 cover=kb.cover, doc_count=kb.doc_count, total_size=kb.total_size,
                 created_at=kb.created_at.isoformat() if kb.created_at else "").model_dump()


@router.get("")
async def list_(me=Depends(get_current_user)):
    return ok([_out(k) for k in await ks.list_kbs(str(me.id))])

@router.get("/{kb_id}")
async def detail(kb_id: str, me=Depends(get_current_user)):
    from sqlalchemy import select
    from app.db.session import async_session
    from app.models.knowledge_base import KnowledgeBase
    async with async_session() as s:
        kb = (await s.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))).scalar_one_or_none()
    return ok(_out(kb))

@router.post("")
async def create(body: KBCreate, me=Depends(get_current_user)):
    kb = await ks.create_kb(str(me.id), body.name, body.description, body.scene, body.cover)
    return ok(_out(kb))

@router.put("/{kb_id}")
async def update(kb_id: str, body: KBUpdate, me=Depends(get_current_user)):
    kb = await ks.update_kb(kb_id, name=body.name, description=body.description, scene=body.scene, cover=body.cover)
    return ok(_out(kb))

@router.delete("/{kb_id}")
async def delete(kb_id: str, me=Depends(get_current_user)):
    await ks.delete_kb(kb_id)
    return ok({"success": True})
```

- [ ] **Step 5: 在 `backend/app/main.py` 挂载** `app.include_router(knowledge.router, prefix=settings.api_prefix)`（import `from app.api.v2 import ..., knowledge`）

- [ ] **Step 6: 测试通过** → `pytest tests/test_knowledge_api.py -v` PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/knowledge_service.py backend/app/schemas/knowledge.py backend/app/api/v2/knowledge.py backend/app/main.py backend/tests/test_knowledge_api.py
git commit -m "feat(knowledge): /knowledge CRUD api"
```

---

### Task 8: ParserDispatcher + 四种解析器（PDF/DOCX/XLSX/MD）

**Files:**
- Create: `backend/app/core/parser/__init__.py`、`models.py`、`dispatcher.py`、`pdf_parser.py`、`docx_parser.py`、`xlsx_parser.py`、`md_parser.py`
- Test: `backend/tests/test_parser.py`

- [ ] **Step 1: 实现 `backend/app/core/parser/models.py`**

```python
from dataclasses import dataclass

@dataclass
class ParsedElement:
    element_type: str        # text/table/image/heading
    content: str             # 文本/表格HTML/标题
    page_number: int
    section_path: str = ""   # 由 TreeBuilder 填充
    image_key: str | None = None
```

- [ ] **Step 2: 实现 `backend/app/core/parser/pdf_parser.py`（PyMuPDF 文本块 + pdfplumber 表格）**

```python
import fitz                      # pymupdf
import pdfplumber
from app.core.parser.models import ParsedElement


async def parse(path: str) -> list[ParsedElement]:
    elements: list[ParsedElement] = []
    doc = fitz.open(path)
    table_pages = _extract_tables(path)            # {page: [html,...]}
    for page in doc:
        pno = page.number + 1
        # 文本块（按块保留顺序）
        for block in page.get_text("blocks"):
            text = (block[4] or "").strip()
            if text:
                elements.append(ParsedElement("text", text, pno))
        # 表格（HTML）
        for html in table_pages.get(pno, []):
            elements.append(ParsedElement("table", html, pno))
    doc.close()
    return elements


def _extract_tables(path: str) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            for t in page.extract_tables() or []:
                out.setdefault(i + 1, []).append(_table_to_html(t))
    return out


def _table_to_html(rows: list[list]) -> str:
    body = "".join("<tr>" + "".join(f"<td>{(c or '')}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table>{body}</table>"
```

- [ ] **Step 3: 实现 `backend/app/core/parser/docx_parser.py`**

```python
from docx import Document as DocxDocument
from app.core.parser.models import ParsedElement


async def parse(path: str) -> list[ParsedElement]:
    elements: list[ParsedElement] = []
    d = DocxDocument(path)
    for para in d.paragraphs:
        txt = (para.text or "").strip()
        if not txt:
            continue
        style = (para.style.name or "").lower()
        etype = "heading" if style.startswith("heading") or style == "title" else "text"
        elements.append(ParsedElement(etype, txt, 1))
    # 表格
    for ti, table in enumerate(d.tables):
        rows = [[c.text for c in row.cells] for row in table.rows]
        body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
        elements.append(ParsedElement("table", f"<table>{body}</table>", 1))
    return elements
```

- [ ] **Step 4: 实现 `backend/app/core/parser/xlsx_parser.py`**

```python
from openpyxl import load_workbook
from app.core.parser.models import ParsedElement


async def parse(path: str) -> list[ParsedElement]:
    elements: list[ParsedElement] = []
    wb = load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        rows = [[("" if c is None else str(c)) for c in row] for row in ws.iter_rows(values_only=True)]
        if not rows:
            continue
        body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
        elements.append(ParsedElement("table", f"<table>{body}</table>", 1, section_path=ws.title))
    wb.close()
    return elements
```

- [ ] **Step 5: 实现 `backend/app/core/parser/md_parser.py`（md/txt 通用）**

```python
import re
from app.core.parser.models import ParsedElement

_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")


async def parse(path: str) -> list[ParsedElement]:
    elements: list[ParsedElement] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            m = _HEADING.match(line)
            if m:
                elements.append(ParsedElement("heading", m.group(2).strip(), 1))
            else:
                elements.append(ParsedElement("text", line, 1))
    return elements
```

- [ ] **Step 6: 实现 `backend/app/core/parser/dispatcher.py`**

```python
from app.core.parser import pdf_parser, docx_parser, xlsx_parser, md_parser
from app.core.parser.models import ParsedElement
from app.exceptions import BizException, ErrorCode


async def parse(ext: str, path: str) -> list[ParsedElement]:
    e = ext.lower().lstrip(".")
    if e == "pdf":
        return await pdf_parser.parse(path)
    if e == "docx":
        return await docx_parser.parse(path)
    if e in ("xlsx", "xls"):
        return await xlsx_parser.parse(path)
    if e in ("md", "txt", "markdown"):
        return await md_parser.parse(path)
    raise BizException(ErrorCode.UNSUPPORTED_FILE, f"不支持的文件格式: {ext}")
```

- [ ] **Step 7: 写测试 `backend/tests/test_parser.py`**

```python
import pytest, os
from app.core.parser.dispatcher import parse
from app.core.parser import md_parser, docx_parser

@pytest.mark.asyncio
async def test_md_parser(tmp_path):
    f = tmp_path / "t.md"; f.write_text("# 标题一\n正文段落\n## 子标题\n更多正文", encoding="utf-8")
    elems = await md_parser.parse(str(f))
    types = [e.element_type for e in elems]
    assert "heading" in types and "text" in types

@pytest.mark.asyncio
async def test_dispatcher_unsupported():
    with pytest.raises(Exception):
        await parse("pptx", "x.pptx")
```

- [ ] **Step 8: 测试通过** → `pytest tests/test_parser.py -v` PASS（PDF/DOCX/XLSX 解析器在集成冒烟时用真实文件验证）

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/parser backend/tests/test_parser.py
git commit -m "feat(parser): dispatcher + pdf/docx/xlsx/md parsers"
```

---

### Task 9: Chunker 结构化分块（含 ParsedElement.level 扩展）

**Files:**
- Modify: `backend/app/core/parser/models.py`（加 level 字段）
- Modify: `backend/app/core/parser/md_parser.py`、`docx_parser.py`（填 level）
- Create: `backend/app/core/parser/chunker.py`
- Test: `backend/tests/test_chunker.py`

- [ ] **Step 1: 扩展 `backend/app/core/parser/models.py` 加 level**

```python
from dataclasses import dataclass

@dataclass
class ParsedElement:
    element_type: str        # text/table/image/heading
    content: str
    page_number: int
    section_path: str = ""
    image_key: str | None = None
    level: int = 0           # heading 层级（1-6）；非 heading 为 0
```

- [ ] **Step 2: 更新 `md_parser.py` 填 level（# 数量）**

将 md_parser 中 heading 分支改为：

```python
            m = _HEADING.match(line)
            if m:
                level = len(m.group(1))            # # 的数量
                elements.append(ParsedElement("heading", m.group(2).strip(), 1, level=level))
```

- [ ] **Step 3: 更新 `docx_parser.py` 填 level（Heading N）**

将 docx_parser 中 heading 判定改为：

```python
        style = (para.style.name or "").lower()
        if style.startswith("heading"):
            # "Heading 2" → level 2
            try: lvl = int(style.split()[-1])
            except ValueError: lvl = 1
            elements.append(ParsedElement("heading", txt, 1, level=lvl))
        else:
            elements.append(ParsedElement("text", txt, 1))
```

- [ ] **Step 4: 写失败测试 `backend/tests/test_chunker.py`**

```python
import pytest
from app.core.parser.models import ParsedElement
from app.core.parser.chunker import chunk

def test_chunk_by_section_and_size():
    elems = [
        ParsedElement("heading", "第一章", 1, level=1),
        ParsedElement("text", "A"*600, 1),     # 超过 chunk_size=512，应切多块
        ParsedElement("heading", "1.1 概述", 2, level=2),
        ParsedElement("text", "B"*100, 2),
    ]
    out = chunk(elems, chunk_size=512, overlap=64)
    assert len(out) >= 2                          # 至少两块
    assert all("section_path" in c for c in out)
    # 第二章下的块 section_path 含 "1.1 概述"
    assert any("1.1 概述" in c["section_path"] for c in out)

def test_empty_elements():
    assert chunk([], 512, 64) == []
```

- [ ] **Step 5: 实现 `backend/app/core/parser/chunker.py`**

```python
from app.core.parser.models import ParsedElement


def chunk(elements: list[ParsedElement], chunk_size: int = 512, overlap: int = 64) -> list[dict]:
    """按 heading 分节，节内按 chunk_size 滑窗切分（overlap）。返回 chunk dict 列表。"""
    result: list[dict] = []
    section_stack: list[tuple[int, str]] = []    # (level, title)
    buf = ""
    buf_page = 1
    seq = 0

    def section_path() -> str:
        return " > ".join(t for _, t in section_stack)

    def flush():
        nonlocal buf, seq
        text = buf.strip()
        if not text:
            buf = ""
            return
        i = 0
        step = max(1, chunk_size - overlap)
        while i < len(text):
            piece = text[i:i + chunk_size]
            result.append({
                "content": piece, "content_search": piece,
                "page_number": buf_page, "section_path": section_path(),
                "clause_title": section_stack[-1][1] if section_stack else None,
                "seq": seq,
            })
            seq += 1
            if i + chunk_size >= len(text):
                break
            i += step
        buf = ""

    for e in elements:
        if e.element_type == "heading" and e.level > 0:
            flush()
            # 弹出同级及更深的标题
            while section_stack and section_stack[-1][0] >= e.level:
                section_stack.pop()
            section_stack.append((e.level, e.content))
        else:
            if not buf:
                buf_page = e.page_number
            buf += ("\n" if buf else "") + e.content
            if len(buf) >= chunk_size:
                flush()
    flush()
    return result
```

- [ ] **Step 6: 测试通过** → `cd backend && pytest tests/test_chunker.py -v` PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/parser/models.py backend/app/core/parser/md_parser.py backend/app/core/parser/docx_parser.py backend/app/core/parser/chunker.py backend/tests/test_chunker.py
git commit -m "feat(parser): section-aware chunker + heading level"
```

---

### Task 10: TreeBuilder 结构树构建

**Files:**
- Create: `backend/app/core/parser/tree_builder.py`
- Test: `backend/tests/test_tree_builder.py`

> 简化：每个 heading 节点的 `page_start=page_end=该 heading 页码`；精确页码范围（覆盖到下一同级标题前）留作优化。`summary` 暂为 title（LLM 摘要按场景可选，后续）。

- [ ] **Step 1: 写失败测试 `backend/tests/test_tree_builder.py`**

```python
import pytest
from sqlalchemy import select
from app.db.session import async_session
from app.core.parser.tree_builder import build_tree
from app.core.parser.models import ParsedElement
from app.models.tree_node import TreeNode
from app.models.document import Document

@pytest.mark.asyncio
async def test_build_hierarchy():
    async with async_session() as s:
        d = (await s.execute(select(Document))).scalars().first()
    elems = [
        ParsedElement("heading", "第一章", 1, level=1),
        ParsedElement("text", "x", 1),
        ParsedElement("heading", "1.1 概述", 2, level=2),
        ParsedElement("heading", "第二章", 3, level=1),
    ]
    nodes = await build_tree(str(d.id), elems)
    levels = [n.level for n in nodes]
    assert 1 in levels and 2 in levels
    # 第二章(1.1 的叔辈)应与第一章同级
    ones = [n for n in nodes if n.level == 1]
    assert len(ones) == 2
    # 1.1 的 parent 是第一章
    child = [n for n in nodes if n.title == "1.1 概述"][0]
    assert child.parent_id == ones[0].id
```

- [ ] **Step 2: 实现 `backend/app/core/parser/tree_builder.py`**

```python
from sqlalchemy import select
from app.db.session import async_session
from app.models.tree_node import TreeNode
from app.core.parser.models import ParsedElement


async def build_tree(doc_id: str, elements: list[ParsedElement]) -> list[TreeNode]:
    """从 heading 元素构建层级树并入库。返回除根外的所有节点。"""
    headings = [e for e in elements if e.element_type == "heading" and e.level > 0]
    async with async_session() as s:
        root = TreeNode(document_id=doc_id, level=0, sort_order=0, title="文档",
                        page_start=headings[0].page_number if headings else 1, page_end=1)
        s.add(root)
        await s.flush()

        stack: list[tuple[int, TreeNode]] = [(0, root)]
        order = 1
        for h in headings:
            while stack and stack[-1][0] >= h.level:
                stack.pop()
            parent = stack[-1][1] if stack else root
            node = TreeNode(document_id=doc_id, parent_id=parent.id, level=h.level,
                            sort_order=order, title=h.content, summary=h.content,
                            page_start=h.page_number, page_end=h.page_number)
            s.add(node)
            await s.flush()
            stack.append((h.level, node))
            order += 1

        await s.commit()
        rows = (await s.execute(select(TreeNode).where(TreeNode.document_id == doc_id)
                                .order_by(TreeNode.sort_order))).scalars().all()
        return [r for r in rows if r.level > 0]
```

- [ ] **Step 3: 测试通过** → `cd backend && pytest tests/test_tree_builder.py -v` PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/parser/tree_builder.py backend/tests/test_tree_builder.py
git commit -m "feat(parser): tree builder (stack-based hierarchy)"
```

---

### Task 11: parse_document_task（ARQ 核心任务）

**Files:**
- Modify: `backend/app/worker/app.py`（加任务 + 注册）
- Test: `backend/tests/test_parse_task.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_parse_task.py`**

```python
import pytest, os
from sqlalchemy import select
from app.db.session import async_session
from app.worker.app import parse_document_task
from app.models.document import Document, ParseTask
from app.models.chunk import Chunk
from app.providers.storage.factory import get_storage
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_parse_task_end_to_end(tmp_path, monkeypatch):
    # 准备：建 doc + 写假文件 + mock embedding
    async with async_session() as s:
        from app.models.knowledge_base import KnowledgeBase
        from app.models.user import User
        u = (await s.execute(select(User))).scalars().first()
        kb = KnowledgeBase(user_id=u.id, name="t", scene="general"); s.add(kb); await s.flush()
        doc = Document(kb_id=kb.id, user_id=u.id, name="t.md", ext="md", size=10, mode="fast",
                       status="pending", file_key=f"{kb.id}/t.md")
        s.add(doc); await s.flush()
        doc.file_key = f"{kb.id}/{doc.id}/t.md"
        task = ParseTask(doc_id=doc.id, kb_id=str(kb.id), status="pending"); s.add(task)
        await s.commit()
        doc_id, key = str(doc.id), doc.file_key

    monkeypatch.setattr("app.config.settings.storage_local_dir", str(tmp_path))
    st = get_storage()
    await st.put(key, "# 标题\n正文内容\n".encode("utf-8"))

    # mock embedding（返回固定向量）
    fake_emb = AsyncMock(); fake_emb.aembed_documents = AsyncMock(return_value=[[0.1]*1024, [0.2]*1024])
    with patch("app.worker.app.build_embeddings", AsyncMock(return_value=fake_emb)):
        await parse_document_task({}, doc_id)

    async with async_session() as s:
        d = (await s.execute(select(Document).where(Document.id == doc_id))).scalar_one()
        assert d.status == "done" and d.pct == 100
        assert d.chunk_count >= 1
        chunks = (await s.execute(select(Chunk).where(Chunk.document_id == doc_id))).scalars().all()
        assert len(chunks) >= 1
        assert chunks[0].embedding is not None
```

- [ ] **Step 2: 重写 `backend/app/worker/app.py`（加任务 + 注册到 functions）**

```python
import os, tempfile
from arq.connections import RedisSettings
from sqlalchemy import select, update
from app.config import settings
from app.db.session import async_session
from app.models.document import Document, ParseTask
from app.models.chunk import Chunk
from app.models.element_position import ElementPosition
from app.models.knowledge_base import KnowledgeBase
from app.providers.storage.factory import get_storage
from app.providers.langchain_factory import build_embeddings
from app.core.parser.dispatcher import parse as parse_file
from app.core.parser.chunker import chunk as do_chunk
from app.core.parser.tree_builder import build_tree


async def _set_status(doc_id: str, status: str, pct: int, error: str | None = None):
    async with async_session() as s:
        await s.execute(update(Document).where(Document.id == doc_id).values(status=status, pct=pct, error=error))
        await s.execute(update(ParseTask).where(ParseTask.doc_id == doc_id).values(status=status, pct=pct, error=error))
        await s.commit()


async def parse_document_task(ctx, doc_id: str):
    """ARQ 任务：解析文档 → 分块 → 建树 → 向量化。失败自动重试（max_tries=3）。"""
    try:
        async with async_session() as s:
            doc = (await s.execute(select(Document).where(Document.id == doc_id))).scalar_one()
            kb = (await s.execute(select(KnowledgeBase).where(KnowledgeBase.id == doc.kb_id))).scalar_one()
            doc_id_s, kb_id_s, ext, file_key = str(doc.id), str(kb.id), doc.ext, doc.file_key
            chunk_size, overlap = kb.chunk_size, kb.chunk_overlap

        await _set_status(doc_id_s, "parsing", 5)

        storage = get_storage()
        data = await storage.get(file_key)
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tf:
            tf.write(data); tmp_path = tf.name

        elements = await parse_file(ext, tmp_path)
        os.unlink(tmp_path)
        await _set_status(doc_id_s, "parsing", 40)

        chunks_data = do_chunk(elements, chunk_size=chunk_size, overlap=overlap)
        await _set_status(doc_id_s, "parsing", 55)

        async with async_session() as s:
            chunk_objs: list[Chunk] = []
            for cd in chunks_data:
                c = Chunk(document_id=doc_id_s, kb_id=kb_id_s, content=cd["content"],
                          content_search=cd["content_search"], page_number=cd["page_number"],
                          section_path=cd["section_path"], clause_title=cd["clause_title"], seq=cd["seq"])
                s.add(c); chunk_objs.append(c)
            await s.flush()
            for i, e in enumerate(elements):
                s.add(ElementPosition(document_id=doc_id_s, element_type=e.element_type, element_index=i,
                                      page_number=e.page_number, content=e.content, metadata_={"section_path": e.section_path}))
            await s.commit()
        await _set_status(doc_id_s, "parsing", 70)

        tree_nodes = await build_tree(doc_id_s, elements)
        await _set_status(doc_id_s, "parsing", 80)

        emb = await build_embeddings()
        if chunk_objs:
            vecs = await emb.aembed_documents([c.content for c in chunk_objs])
            async with async_session() as s:
                for c, v in zip(chunk_objs, vecs):
                    await s.execute(update(Chunk).where(Chunk.id == c.id).values(embedding=v, embedding_model="default"))
                await s.commit()
        if tree_nodes:
            nav_vecs = await emb.aembed_documents([n.title for n in tree_nodes])
            async with async_session() as s:
                for n, v in zip(tree_nodes, nav_vecs):
                    await s.execute(update(TreeNode).where(TreeNode.id == n.id).values(nav_embedding=v))   # noqa: F821
                await s.commit()

        async with async_session() as s:
            await s.execute(update(Document).where(Document.id == doc_id_s).values(
                status="done", pct=100, chunk_count=len(chunk_objs), element_count=len(elements)))
            await s.commit()
        await _set_status(doc_id_s, "done", 100)
    except Exception as e:
        await _set_status(doc_id_s, "failed", 100, error=str(e))
        raise


class WorkerSettings:
    functions = [parse_document_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 4
    job_timeout = 600
    max_tries = 3
```

> 注意：`update(TreeNode)` 需在文件顶部补 `from app.models.tree_node import TreeNode` import。

- [ ] **Step 3: 补 import**（在 `app/worker/app.py` 顶部追加）

```python
from app.models.tree_node import TreeNode
```

- [ ] **Step 4: 测试通过** → `cd backend && pytest tests/test_parse_task.py -v` PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/worker/app.py backend/tests/test_parse_task.py
git commit -m "feat(worker): parse_document_task (parse→chunk→tree→embed)"
```

---

### Task 12: documents 上传 + 列表 + 详情 + 删除 API

**Files:**
- Create: `backend/app/schemas/document.py`、`backend/app/api/v2/documents.py`
- Modify: `backend/app/main.py`（挂载）
- Test: `backend/tests/test_documents_api.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_documents_api.py`**

```python
import pytest, io
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token
from app.models.user import User
from app.models.knowledge_base import KnowledgeBase
from sqlalchemy import select
from app.db.session import async_session
from unittest.mock import AsyncMock, patch

@pytest.fixture(scope="module", autouse=True)
async def _admin(): await ensure_admin()

async def _token():
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
    return create_access_token(u.id)

@pytest.mark.asyncio
async def test_upload_returns_task_and_doc(monkeypatch, tmp_path):
    async with async_session() as s:
        kb = (await s.execute(select(KnowledgeBase))).scalars().first()
        kb_id = str(kb.id)
    monkeypatch.setattr("app.config.settings.storage_local_dir", str(tmp_path))
    fake_pool = AsyncMock(); fake_pool.enqueue_job = AsyncMock()
    with patch("app.api.v2.documents.create_pool", AsyncMock(return_value=fake_pool)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            tok = await _token()
            r = await c.post("/api/v2/documents/upload",
                             headers={"Authorization": f"Bearer {tok}"},
                             files={"file": ("t.md", io.BytesIO(b"# h\n正文"), "text/markdown")},
                             data={"kbId": kb_id, "mode": "fast"})
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["task_id"] and body["data"]["doc_id"]
    fake_pool.enqueue_job.assert_called_once()
```

- [ ] **Step 2: 实现 `backend/app/schemas/document.py`**

```python
from pydantic import BaseModel

class DocOut(BaseModel):
    id: str
    kb_id: str
    name: str
    ext: str
    size: int
    status: str
    pct: int = 0
    mode: str = "fast"
    pages: int = 0
    element_count: int = 0
    created_at: str = ""
```

- [ ] **Step 3: 实现 `backend/app/api/v2/documents.py`**

```python
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from arq import create_pool
from arq.connections import RedisSettings
from app.api.deps import get_current_user
from app.api.response import ok
from app.config import settings
from app.db.session import async_session
from app.db.redis import get_redis
from app.models.document import Document, ParseTask
from app.models.knowledge_base import KnowledgeBase
from app.providers.storage.factory import get_storage
from app.schemas.document import DocOut
from app.exceptions import BizException, ErrorCode

router = APIRouter(tags=["documents"])

ALLOWED_EXT = {"pdf", "docx", "doc", "xlsx", "xls", "md", "txt", "markdown"}
MAX_SIZE = 50 * 1024 * 1024


def _out(d: Document) -> dict:
    return DocOut(id=str(d.id), kb_id=str(d.kb_id), name=d.name, ext=d.ext, size=d.size,
                  status=d.status, pct=d.pct, mode=d.mode, pages=d.pages,
                  element_count=d.element_count,
                  created_at=d.created_at.isoformat() if d.created_at else "").model_dump()


@router.post("/documents/upload")
async def upload(file: UploadFile = File(...), kbId: str = Form(...), mode: str = Form("fast"),
                 scene: str | None = Form(None), me=Depends(get_current_user)):
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        raise BizException(ErrorCode.UNSUPPORTED_FILE, f"不支持的格式: {ext}")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise BizException(ErrorCode.FILE_TOO_LARGE, "文件超过 50MB 限制")

    async with async_session() as s:
        kb = (await s.execute(select(KnowledgeBase).where(KnowledgeBase.id == kbId))).scalar_one_or_none()
        if not kb:
            raise BizException(ErrorCode.NOT_FOUND, "知识库不存在")
        doc = Document(kb_id=kbId, user_id=str(me.id), name=file.filename, ext=ext, size=len(data),
                       mode=mode, status="pending", file_key="")  # 临时空，flush 拿 id 后覆盖为真实 key
        s.add(doc); await s.flush()
        doc.file_key = f"{kbId}/{doc.id}/{file.filename}"
        task = ParseTask(doc_id=doc.id, kb_id=kbId, status="pending")
        s.add(task)
        await s.commit(); await s.refresh(doc); await s.refresh(task)
        doc_id, key, task_id = str(doc.id), doc.file_key, str(task.id)

    storage = get_storage()
    await storage.put(key, data)

    redis = await get_redis()
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job("parse_document_task", doc_id)

    return ok({"task_id": task_id, "doc_id": doc_id})


@router.get("/documents")
async def list_docs(kb_id: str = Query(...), me=Depends(get_current_user)):
    async with async_session() as s:
        rows = (await s.execute(select(Document).where(Document.kb_id == kb_id).order_by(Document.created_at.desc()))).scalars().all()
    return ok({"list": [_out(r) for r in rows], "total": len(rows)})


@router.get("/documents/{doc_id}")
async def detail(doc_id: str, me=Depends(get_current_user)):
    async with async_session() as s:
        d = (await s.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
    if not d:
        raise BizException(ErrorCode.NOT_FOUND, "文档不存在")
    return ok(_out(d))


@router.delete("/documents/{doc_id}")
async def delete_doc(doc_id: str, me=Depends(get_current_user)):
    async with async_session() as s:
        d = (await s.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
        if not d:
            raise BizException(ErrorCode.NOT_FOUND, "文档不存在")
        key = d.file_key
        await s.execute(delete(Document).where(Document.id == doc_id))
        await s.commit()
    storage = get_storage()
    await storage.delete(key)
    return ok({"success": True})
```

- [ ] **Step 4: 在 `backend/app/main.py` 挂载** `app.include_router(documents.router, prefix=settings.api_prefix)`

- [ ] **Step 5: 测试通过** → `cd backend && pytest tests/test_documents_api.py -v` PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/document.py backend/app/api/v2/documents.py backend/app/main.py backend/tests/test_documents_api.py
git commit -m "feat(documents): upload(multipart)+list+detail+delete api"
```

---

### Task 13: parse-tasks 轮询 API

**Files:**
- Create: `backend/app/api/v2/parse_tasks.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_parse_tasks_api.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_parse_tasks_api.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token
from app.models.user import User
from app.models.document import Document, ParseTask
from sqlalchemy import select
from app.db.session import async_session

@pytest.fixture(scope="module", autouse=True)
async def _admin(): await ensure_admin()

async def _token():
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
    return create_access_token(u.id)

@pytest.mark.asyncio
async def test_get_parse_task():
    async with async_session() as s:
        d = (await s.execute(select(Document))).scalars().first()
        t = ParseTask(doc_id=d.id, kb_id=str(d.kb_id), status="parsing", pct=50); s.add(t); await s.commit()
        tid = str(t.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(f"/api/v2/parse-tasks/{tid}", headers={"Authorization": f"Bearer {await _token()}"})
    body = r.json()["data"]
    assert body["status"] == "parsing" and body["pct"] == 50
```

- [ ] **Step 2: 实现 `backend/app/api/v2/parse_tasks.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.document import ParseTask
from app.exceptions import BizException, ErrorCode

router = APIRouter(tags=["parse-tasks"])


@router.get("/parse-tasks/{task_id}")
async def get_task(task_id: str, me=Depends(get_current_user)):
    async with async_session() as s:
        t = (await s.execute(select(ParseTask).where(ParseTask.id == task_id))).scalar_one_or_none()
    if not t:
        raise BizException(ErrorCode.NOT_FOUND, "解析任务不存在")
    return ok({"task_id": str(t.id), "doc_id": str(t.doc_id), "status": t.status, "pct": t.pct, "error": t.error})
```

- [ ] **Step 3: 挂载** `app.include_router(parse_tasks.router, prefix=settings.api_prefix)`

- [ ] **Step 4: 测试通过** → `cd backend && pytest tests/test_parse_tasks_api.py -v` PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v2/parse_tasks.py backend/app/main.py backend/tests/test_parse_tasks_api.py
git commit -m "feat(documents): /parse-tasks/:id polling api"
```

---

### Task 14: tree API（/documents/:id/tree）

**Files:**
- Create: `backend/app/api/v2/tree.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_tree_api.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_tree_api.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token
from app.core.parser.tree_builder import build_tree
from app.core.parser.models import ParsedElement
from app.models.document import Document
from app.models.tree_node import TreeNode
from sqlalchemy import select
from app.db.session import async_session

@pytest.fixture(scope="module", autouse=True)
async def _admin(): await ensure_admin()

@pytest.mark.asyncio
async def test_tree_nested_shape():
    async with async_session() as s:
        d = (await s.execute(select(Document))).scalars().first()
        doc_id = str(d.id)
    await build_tree(doc_id, [
        ParsedElement("heading", "第一章", 1, level=1),
        ParsedElement("heading", "1.1 子", 1, level=2),
    ])
    from app.models.user import User
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
    tok = create_access_token(u.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(f"/api/v2/documents/{doc_id}/tree", headers={"Authorization": f"Bearer {tok}"})
    tree = r.json()["data"]["tree"]
    assert len(tree) == 1 and tree[0]["title"] == "第一章"
    assert len(tree[0]["children"]) == 1 and tree[0]["children"][0]["title"] == "1.1 子"
```

- [ ] **Step 2: 实现 `backend/app/api/v2/tree.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.tree_node import TreeNode
from app.exceptions import BizException, ErrorCode

router = APIRouter(tags=["tree"])


@router.get("/documents/{doc_id}/tree")
async def get_tree(doc_id: str, me=Depends(get_current_user)):
    async with async_session() as s:
        nodes = (await s.execute(select(TreeNode).where(TreeNode.document_id == doc_id).order_by(TreeNode.sort_order))).scalars().all()
    if not nodes:
        raise BizException(ErrorCode.NOT_FOUND, "结构树尚未生成或文档不存在")
    by_parent: dict[str, list] = {}
    for n in nodes:
        key = str(n.parent_id) if n.parent_id else "root"
        by_parent.setdefault(key, []).append(n)

    def build(parent_key: str):
        return [{"node_id": str(n.id), "title": n.title, "level": n.level,
                 "summary": n.summary, "element_count": n.element_count,
                 "children": build(str(n.id))} for n in by_parent.get(parent_key, [])]

    return ok({"document_id": doc_id, "title": by_parent.get("root", [None])[0].title if by_parent.get("root") else "",
               "tree": build("root")})
```

- [ ] **Step 3: 挂载** `app.include_router(tree.router, prefix=settings.api_prefix)`

- [ ] **Step 4: 测试通过** → `cd backend && pytest tests/test_tree_api.py -v` PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v2/tree.py backend/app/main.py backend/tests/test_tree_api.py
git commit -m "feat(documents): /documents/:id/tree nested tree api"
```

---

### Task 15: elements API（/documents/:id/elements）

**Files:**
- Create: `backend/app/api/v2/elements_list.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_elements_list_api.py`

> 这是**文档内元素列表**（前端知识库详情页用）。引用懒加载的 `GET /elements/:id`（完整 DocElement 字段）在 Plan 6 实现。

- [ ] **Step 1: 写失败测试 `backend/tests/test_elements_list_api.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token
from app.models.user import User
from app.models.element_position import ElementPosition
from app.models.document import Document
from sqlalchemy import select
from app.db.session import async_session

@pytest.fixture(scope="module", autouse=True)
async def _admin(): await ensure_admin()

@pytest.mark.asyncio
async def test_list_elements():
    async with async_session() as s:
        d = (await s.execute(select(Document))).scalars().first()
        doc_id = str(d.id)
        s.add(ElementPosition(document_id=d.id, element_type="text", element_index=0, page_number=1, content="A"))
        s.add(ElementPosition(document_id=d.id, element_type="table", element_index=1, page_number=1, content="<table/>"))
        await s.commit()
        u = (await s.execute(select(User))).scalars().first()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(f"/api/v2/documents/{doc_id}/elements", headers={"Authorization": f"Bearer {create_access_token(u.id)}"})
    data = r.json()["data"]
    assert data["total"] >= 2
    assert all("element_id" in e and "type" in e for e in data["list"])
```

- [ ] **Step 2: 实现 `backend/app/api/v2/elements_list.py`**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.element_position import ElementPosition

router = APIRouter(tags=["elements"])


@router.get("/documents/{doc_id}/elements")
async def list_elements(doc_id: str, page: int = 1, page_size: int = 50,
                        type: str | None = Query(None), me=Depends(get_current_user)):
    async with async_session() as s:
        q = select(ElementPosition).where(ElementPosition.document_id == doc_id)
        if type:
            q = q.where(ElementPosition.element_type == type)
        total = (await s.execute(select(func.count()).select_from(q.subquery()))).scalar()
        rows = (await s.execute(q.order_by(ElementPosition.element_index)
                                .limit(page_size).offset((page - 1) * page_size))).scalars().all()
    return ok({"list": [{"element_id": str(e.id), "type": e.element_type, "content": e.content,
                         "page_number": e.page_number, "section_path": (e.metadata_ or {}).get("section_path", "")}
                        for e in rows], "total": total})
```

- [ ] **Step 3: 挂载** `app.include_router(elements_list.router, prefix=settings.api_prefix)`

- [ ] **Step 4: 测试通过** → `cd backend && pytest tests/test_elements_list_api.py -v` PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v2/elements_list.py backend/app/main.py backend/tests/test_elements_list_api.py
git commit -m "feat(documents): /documents/:id/elements list api"
```

---

### Task 16: 端到端冒烟（上传→轮询→tree/elements）

**Files:**
- 无新增，运行集成验证

- [ ] **Step 1: 全量测试**

Run: `cd backend && pytest -v`
Expected: Plan 1 + Plan 2 + Plan 3 所有测试 passed。

- [ ] **Step 2: Docker 全栈重启（含 worker）**

Run: `cd deploy && docker compose up -d --build && sleep 15`
Expected: postgres/redis/backend/worker 全 healthy/running；worker 日志含 `Starting worker`。

- [ ] **Step 3: 真实文档上传端到端**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v2/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
# 先建知识库
KB=$(curl -s -X POST http://localhost:8000/api/v2/knowledge -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name":"测试KB","scene":"general"}' | python -c "import sys,json;print(json.load(sys.stdin)['data']['id'])")
# 上传一个 md 文档（需确保 settings 已配 embedding 模型，否则解析任务向量化失败）
curl -s -X POST http://localhost:8000/api/v2/documents/upload -H "Authorization: Bearer $TOKEN" \
  -F "file=@some-doc.md" -F "kbId=$KB" -F "mode=fast"
```
Expected: 返回 `{task_id, doc_id}`。

- [ ] **Step 4: 轮询解析进度直到 done**

```bash
TASK=<上一步 task_id>
# 每 2s 轮询
curl -s "http://localhost:8000/api/v2/parse-tasks/$TASK" -H "Authorization: Bearer $TOKEN"
# 重复直到 status=done, pct=100
```
Expected: 最终 `status:"done", pct:100`；若 `failed`，查 `error`（常见：未配 embedding 模型 → 先在 settings 配一个）。

- [ ] **Step 5: 查看结构树与元素**

```bash
DOC=<上一步 doc_id>
curl -s "http://localhost:8000/api/v2/documents/$DOC/tree" -H "Authorization: Bearer $TOKEN"
curl -s "http://localhost:8000/api/v2/documents/$DOC/elements" -H "Authorization: Bearer $TOKEN"
```
Expected: tree 返回嵌套章节树；elements 返回元素列表。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "test: phase1 knowledge/parsing e2e smoke (upload→poll→tree/elements)"
```

---

## Plan 3 完成标志

- ✅ 6 张业务表 + 迁移 + 向量/全文索引（chunks ivfflat+pg_trgm、tree_nodes nav_embedding）
- ✅ `/knowledge` CRUD、`/documents/upload`(multipart)+list+detail+delete、`/parse-tasks/:id`
- ✅ ARQ worker 异步解析：PDF/DOCX/XLSX/MD → 结构化分块 → 结构树 → 批量向量化（chunks + nav_embedding）
- ✅ `/documents/:id/tree`（嵌套树）、`/documents/:id/elements`（元素列表）
- ✅ Storage 抽象（本地 FS，预留 MinIO）
- ✅ 端到端：上传文档 → 轮询进度 → 查看树/元素

**下一步**：Plan 4（RAG 检索管线）—— 用此处产出的 chunks 表 + embedding 实现 vector + pg_trgm + RRF + 条件 Rerank + HybridRetriever。

---

*— 计划结束 —*

# Knowledge Base Metadata And Retrieval Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement dual-scope metadata, per-knowledge-base retrieval configuration, and saved retrieval test sets with asynchronous batch metrics.

**Architecture:** Extend the existing SQLAlchemy/FastAPI models and retrieval pipeline instead of replacing them. Metadata schema and retrieval settings are normalized service layers over JSONB storage; retrieval search keeps pgvector/pg_trgm SQL but adds enabled and schema-validated metadata predicates. Retrieval tests are persisted test sets, runs, and case results executed by a background task and measured by pure metric functions. The Vue 3 frontend keeps Mock-first contracts in `types/api/mock/store`, then replaces the current knowledge detail page with five tabbed workflows.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, PostgreSQL JSONB/pgvector/pg_trgm, ARQ, Pydantic v2, pytest, Vue 3, TypeScript, Pinia, Element Plus, Vite.

**Source spec:** `docs/superpowers/specs/2026-08-17-knowledge-base-metadata-retrieval-testing-design.md`.

---

## Execution Rules

1. Implement in a clean worktree on branch `codex/kb-metadata-retrieval-testing`. Do not modify or stage unrelated dirty files in the original worktree.
2. Run backend commands from `backend/`; run frontend commands from `frontend/`.
3. Each task must end with its listed tests passing and a focused commit. Do not combine unrelated changes.
4. Never read or return `ModelConfig.api_key_enc` to the frontend. API keys stay server-only.
5. Preserve the existing API envelope `{ code, message, data }`.
6. V1 embedding vectors remain exactly `EMBEDDING_DIM = 1024`; incompatible model IDs must be rejected when saved.

## File Structure

```text
backend/alembic/versions/
  b71d0c8f4aa2_kb_metadata_retrieval_testing.py

backend/app/models/
  knowledge_base.py                         # Add model bindings and retrieval_config
  document.py                               # Add metadata/enabled/recall_count
  chunk.py                                  # Add metadata/enabled/recall_count/char_count
  metadata.py                               # New KbMetadataField
  retrieval_testing.py                      # New test set/case/run/result models
  __init__.py                               # Import new models

backend/app/schemas/
  knowledge.py                              # Metadata and retrieval-setting contracts
  retrieval_testing.py                      # New test-set/case/run contracts

backend/app/services/
  metadata_service.py                       # Schema CRUD, validation, defaults, impact
  asset_service.py                          # Document/chunk list, metadata, status, filters
  retrieval_settings_service.py             # Effective config and source resolution
  retrieval_test_service.py                 # Sets/cases/runs persistence

backend/app/core/retrieval/
  metadata_filter.py                        # Safe SQL predicate construction
  vector_search.py                          # Add enabled/metadata/result enrichment
  fulltext_search.py                        # Add enabled/metadata/result enrichment
  pipeline.py                               # Use resolved config/model bindings/modes
  test_metrics.py                           # Pure Hit/Recall/MRR/latency metrics

backend/app/api/v2/
  metadata.py                               # Metadata-field routes
  assets.py                                 # Document/chunk metadata routes
  retrieval_settings.py                     # KB retrieval settings routes
  retrieval_testing.py                      # Test-set and run routes
  main.py is backend/app/main.py            # Register new routers

backend/app/providers/langchain_factory.py  # Build embeddings/reranker from explicit config
backend/app/worker/app.py                   # KB-bound embedding and reembed task

backend/tests/
  test_kb_metadata_models.py
  test_metadata_service.py
  test_metadata_api.py
  test_asset_metadata_api.py
  test_retrieval_settings_service.py
  test_retrieval_settings_api.py
  test_retrieval_search_filters.py
  test_retrieval_test_metrics.py
  test_retrieval_testing_api.py
  test_reembedding_worker.py

frontend/src/types/knowledge.ts             # Extended contracts
frontend/src/api/knowledge.ts               # New API functions
frontend/src/mock/knowledge.ts              # Full Mock state and handlers
frontend/src/mock/index.ts                  # Dispatch new knowledge routes
frontend/src/stores/knowledge.ts            # Tab state and actions

frontend/src/views/knowledge/
  KbDetailView.vue                          # Five-tab shell
  components/DocumentsTab.vue
  components/SegmentsTab.vue
  components/MetadataTab.vue
  components/RetrievalSettingsTab.vue
  components/RetrievalTestingTab.vue
  components/MetadataEditor.vue
  components/MetadataFieldDialog.vue
  components/TestSetList.vue
  components/TestCaseTable.vue
  components/TestRunPanel.vue
```

---

### Task 1: Data Model And Migration

**Files:**
- Modify: `backend/app/models/knowledge_base.py`
- Modify: `backend/app/models/document.py`
- Modify: `backend/app/models/chunk.py`
- Create: `backend/app/models/metadata.py`
- Create: `backend/app/models/retrieval_testing.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/b71d0c8f4aa2_kb_metadata_retrieval_testing.py`
- Test: `backend/tests/test_kb_metadata_models.py`

- [ ] **Step 1: Write failing persistence tests**

Create `backend/tests/test_kb_metadata_models.py`:

```python
"""Persistence tests for KB metadata and retrieval testing models."""
import uuid

import pytest
from sqlalchemy import delete, select

from app.db.session import async_session
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.metadata import KbMetadataField
from app.models.retrieval_testing import (
    RetrievalTestCase,
    RetrievalTestCaseResult,
    RetrievalTestRun,
    RetrievalTestSet,
)
from app.models.user import User


async def _admin_id() -> uuid.UUID:
    async with async_session() as s:
        return (await s.execute(select(User))).scalars().first().id


@pytest.mark.asyncio
async def test_metadata_and_assets_persist():
    user_id = await _admin_id()
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "PlanMetaModelKB"))
        await s.commit()
        kb = KnowledgeBase(
            user_id=user_id,
            name="PlanMetaModelKB",
            scene="general",
            retrieval_config={"method": "hybrid"},
        )
        s.add(kb)
        await s.flush()
        s.add(KbMetadataField(
            kb_id=kb.id,
            key="source",
            name="来源",
            scope="document",
            data_type="select",
            options=["招标文件", "投标文件"],
            filterable=True,
            retrieval_filterable=True,
        ))
        doc = Document(
            kb_id=kb.id,
            user_id=user_id,
            name="a.pdf",
            ext="pdf",
            size=10,
            file_key="a",
            metadata={"source": "招标文件"},
            enabled=True,
            recall_count=2,
        )
        s.add(doc)
        await s.commit()
        kb_id, doc_id = kb.id, doc.id

    async with async_session() as s:
        saved_kb = await s.get(KnowledgeBase, kb_id)
        saved_doc = await s.get(Document, doc_id)
        field = (await s.execute(select(KbMetadataField).where(
            KbMetadataField.kb_id == kb_id,
            KbMetadataField.key == "source",
        ))).scalar_one()
        assert saved_kb.retrieval_config["method"] == "hybrid"
        assert saved_doc.metadata_["source"] == "招标文件"
        assert saved_doc.enabled is True
        assert saved_doc.recall_count == 2
        assert field.scope == "document"


@pytest.mark.asyncio
async def test_retrieval_test_tables_persist():
    user_id = await _admin_id()
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "PlanTestModelKB"))
        await s.commit()
        kb = KnowledgeBase(user_id=user_id, name="PlanTestModelKB", scene="general")
        test_set = RetrievalTestSet(kb_id=kb.id, name="回归集")
        case = RetrievalTestCase(
            test_set_id=test_set.id,
            query="质保期要求",
            expected_doc_ids=[str(uuid.uuid4())],
            expected_chunk_ids=[],
            tags=["合同"],
        )
        run = RetrievalTestRun(
            test_set_id=test_set.id,
            kb_id=kb.id,
            status="pending",
            config_snapshot={"method": "hybrid"},
            total_cases=1,
        )
        result = RetrievalTestCaseResult(
            run_id=run.id,
            case_id=case.id,
            query="质保期要求",
            status="pending",
            expected_doc_ids=case.expected_doc_ids,
        )
        s.add_all([kb, test_set, case, run, result])
        await s.commit()
        ids = (test_set.id, case.id, run.id, result.id)

    async with async_session() as s:
        saved_set = await s.get(RetrievalTestSet, ids[0])
        saved_case = await s.get(RetrievalTestCase, ids[1])
        saved_run = await s.get(RetrievalTestRun, ids[2])
        saved_result = await s.get(RetrievalTestCaseResult, ids[3])
        assert saved_set.name == "回归集"
        assert saved_case.tags == ["合同"]
        assert saved_run.config_snapshot["method"] == "hybrid"
        assert saved_result.status == "pending"
```

- [ ] **Step 2: Run tests and verify failure**

Run from `backend/`:

```powershell
pytest tests/test_kb_metadata_models.py -v
```

Expected: import failures for `app.models.metadata` and `app.models.retrieval_testing`, plus unknown model fields.

- [ ] **Step 3: Add model fields and new ORM models**

Use these exact column definitions.

`KnowledgeBase` additions:

```python
embedding_model_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True
)
rerank_model_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True
)
retrieval_config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
```

`Document` additions. SQLAlchemy reserves the Python name `metadata`, so the ORM attribute is `metadata_` while the database column remains `metadata`:

```python
metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default="{}")
enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
recall_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
```

`Chunk` additions use the same mapping:

```python
metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default="{}")
enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
recall_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
char_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
```

Create `backend/app/models/metadata.py`:

```python
"""Knowledge-base metadata field ORM model."""
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class KbMetadataField(Base, UUIDPk, TimestampMixin):
    """Configurable metadata field for document or chunk assets."""

    __tablename__ = "kb_metadata_fields"
    __table_args__ = (
        UniqueConstraint("kb_id", "scope", "key", name="uq_kb_metadata_scope_key"),
    )

    kb_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    scope: Mapped[str] = mapped_column(String(16))
    data_type: Mapped[str] = mapped_column(String(16))
    options: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    default_value: Mapped[dict | list | str | float | bool | None] = mapped_column(JSONB, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    filterable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    retrieval_filterable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    visible: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    built_in: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    mapped_field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
```

Create `backend/app/models/retrieval_testing.py` with the four tables from the spec. Use UUID foreign keys, `JSONB` for all array/object fields, and these statuses:

```python
RUN_STATUSES = {"pending", "running", "completed", "failed", "canceled"}
CASE_RESULT_STATUSES = {"pending", "running", "hit", "partial_hit", "miss", "failed", "skipped"}
```

Include exactly these tables and columns:

```text
RetrievalTestSet: id, kb_id, name, description, archived, created_at, updated_at
RetrievalTestCase: id, test_set_id, query, expected_doc_ids, expected_chunk_ids,
                   tags, enabled, sort_order, created_at, updated_at
RetrievalTestRun: id, test_set_id, kb_id, status, config_snapshot, override_config,
                  total_cases, completed_cases, metrics, error, started_at,
                  finished_at, created_at
RetrievalTestCaseResult: id, run_id, case_id, query, status, expected_doc_ids,
                         hit_doc_ids, results, metrics, latency_ms, error,
                         created_at
```

Add both modules to `backend/app/models/__init__.py`.

- [ ] **Step 4: Create migration `b71d0c8f4aa2`**

The migration must:

1. Add the three `knowledge_bases` columns and two foreign keys.
2. Add the three `documents` columns.
3. Add the four `chunks` columns.
4. Create all four retrieval-testing tables with their foreign keys and indexes.
5. Create `kb_metadata_fields` with its unique constraint.
6. Create `uq_retrieval_test_runs_active` as a partial unique index on
   `retrieval_test_runs(test_set_id)` where `status IN ('pending', 'running')`.
7. Seed six document built-ins for every existing KB:
   `document_name -> name`, `file_size -> size`, `uploader -> user_id`,
   `upload_date -> created_at`, `last_update_date -> updated_at`, and stored
   `source -> NULL`.

Use server defaults from Step 3 so existing rows backfill without data copy. The migration revision is:

```python
revision = "b71d0c8f4aa2"
down_revision = "71dc230762db"
```

- [ ] **Step 5: Run model tests and migration checks**

```powershell
pytest tests/test_kb_metadata_models.py -v
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Expected: all commands pass; downgrade drops only objects created by this revision and restores the previous schema.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/models backend/alembic/versions/b71d0c8f4aa2_kb_metadata_retrieval_testing.py backend/tests/test_kb_metadata_models.py
git commit -m "feat: add KB metadata and retrieval testing schema"
```

---

### Task 2: Metadata Schema Service And API

**Files:**
- Create: `backend/app/services/metadata_service.py`
- Modify: `backend/app/schemas/knowledge.py`
- Create: `backend/app/api/v2/metadata.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_metadata_service.py`
- Test: `backend/tests/test_metadata_api.py`

- [ ] **Step 1: Write failing service tests**

Create `backend/tests/test_metadata_service.py`:

```python
"""Metadata schema validation and CRUD service tests."""
import uuid

import pytest
from sqlalchemy import delete, select

from app.db.session import async_session
from app.models.chunk import Chunk
from app.models.document import Document
from app.exceptions import BizException
from app.models.knowledge_base import KnowledgeBase
from app.models.metadata import KbMetadataField
from app.models.user import User
from app.services.metadata_service import (
    ensure_default_fields,
    validate_metadata,
    create_field,
    delete_field,
)


async def _kb(name: str) -> tuple[str, uuid.UUID]:
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == name))
        await s.commit()
        user = (await s.execute(select(User))).scalars().first()
        kb = KnowledgeBase(user_id=user.id, name=name, scene="general")
        s.add(kb)
        await s.commit()
        return str(kb.id), user.id


async def _chunk_with_metadata(kb_id: str, metadata: dict) -> str:
    async with async_session() as s:
        user = (await s.execute(select(User))).scalars().first()
        doc = Document(
            kb_id=kb_id,
            user_id=user.id,
            name="条款文档.pdf",
            ext="pdf",
            size=10,
            file_key="terms",
            status="done",
        )
        s.add(doc)
        await s.flush()
        chunk = Chunk(
            document_id=doc.id,
            kb_id=kb_id,
            content="乙方应提供三年质保",
            content_search="乙方应提供三年质保",
            metadata_=metadata,
        )
        s.add(chunk)
        await s.commit()
        return str(chunk.id)


@pytest.mark.asyncio
async def test_default_document_fields_are_created_once():
    kb_id, _ = await _kb("PlanMetaDefaultKB")
    await ensure_default_fields(kb_id)
    await ensure_default_fields(kb_id)
    async with async_session() as s:
        kb = await s.get(KnowledgeBase, kb_id)
        fields = (await s.execute(select(KbMetadataField).where(
            KbMetadataField.kb_id == kb.id
        ))).scalars().all()
        assert len(fields) == 6
        assert all(f.built_in for f in fields)


@pytest.mark.asyncio
async def test_validate_metadata_type_and_required():
    kb_id, user_id = await _kb("PlanMetaValidateKB")
    field = await create_field(
        kb_id=kb_id,
        user_id=user_id,
        key="effective_date",
        name="生效日期",
        scope="chunk",
        data_type="date",
        required=True,
    )
    assert str(field.kb_id) == kb_id
    with pytest.raises(BizException):
        await validate_metadata(
            kb_id=kb_id,
            scope="chunk",
            payload={"effective_date": "not-a-date"},
        )
    clean = await validate_metadata(
        kb_id=kb_id,
        scope="chunk",
        payload={"effective_date": "2026-08-17"},
        require_complete=True,
    )
    assert clean == {"effective_date": "2026-08-17"}


@pytest.mark.asyncio
async def test_custom_field_delete_requires_force_when_values_exist():
    kb_id, user_id = await _kb("PlanMetaDeleteKB")
    field = await create_field(
        kb_id=kb_id,
        user_id=user_id,
        key="clause_type",
        name="条款类型",
        scope="chunk",
        data_type="select",
        options=["义务", "权利"],
    )
    await _chunk_with_metadata(kb_id, {"clause_type": "义务"})
    impact = await delete_field(field.id, user_id=user_id, force=False)
    assert impact == {"success": False, "affected_count": 1}
    impact = await delete_field(field.id, user_id=user_id, force=True)
    assert impact == {"success": True, "affected_count": 1}
```

- [ ] **Step 2: Implement `metadata_service.py`**

Public API:

```python
BUILTIN_DOCUMENT_FIELDS = [
    {"key": "document_name", "name": "文档名", "mapped_field": "name"},
    {"key": "file_size", "name": "大小", "mapped_field": "size"},
    {"key": "uploader", "name": "上传人", "mapped_field": "user_id"},
    {"key": "upload_date", "name": "上传时间", "mapped_field": "created_at"},
    {"key": "last_update_date", "name": "更新时间", "mapped_field": "updated_at"},
    {"key": "source", "name": "来源", "mapped_field": None},
]

async def ensure_default_fields(kb_id) -> None
async def list_fields(kb_id, user_id, scope: str | None = None) -> list[KbMetadataField]
async def create_field(*, kb_id, user_id, key, name, scope, data_type, options=None,
                       default_value=None, required=False, filterable=False,
                       retrieval_filterable=False, visible=True, sort_order=0) -> KbMetadataField
async def update_field(field_id, user_id, **changes) -> KbMetadataField
async def delete_field(field_id, user_id, force=False) -> dict
async def validate_metadata(*, kb_id, scope, payload, fields=None,
                      require_complete=False, partial=False) -> dict
```

Hard rules:

1. `key` matches `^[a-z][a-z0-9_]{0,63}$`.
2. `scope` is exactly `document` or `chunk`.
3. `data_type` is exactly `string`, `number`, `date`, `select`, or `boolean`.
4. `select.options` is a nonempty, unique string list.
5. `required` is not editable on built-ins.
6. Built-ins cannot be deleted; custom fields cannot change `key`, `scope`, or `data_type`.
7. `validate_metadata` ignores non-schema keys and rejects type mismatches.
8. Date values use `YYYY-MM-DD`; booleans must be JSON booleans; numbers must be int/float and not bool.
9. `delete_field` counts matching JSON keys in the correct scope. If count is greater than zero and `force=False`, return `{"success": False, "affected_count": count}`; otherwise delete and return `{"success": True, "affected_count": count}`.
10. All field queries join the owning KB and verify `knowledge_bases.user_id == user_id`.

Runtime seeding:

1. migration seeds existing KBs;
2. `knowledge_service.create_kb` calls `ensure_default_fields(kb_id)` in the same transaction;
3. `GET /knowledge/{kb_id}/metadata-fields` also calls `ensure_default_fields(kb_id)` idempotently, covering databases that received the schema outside Alembic.

- [ ] **Step 3: Add schemas and routes**

Add to `backend/app/schemas/knowledge.py`:

```python
class MetadataFieldCreate(BaseModel):
    key: str
    name: str
    scope: Literal["document", "chunk"]
    data_type: Literal["string", "number", "date", "select", "boolean"]
    options: list[str] = []
    default_value: object | None = None
    required: bool = False
    filterable: bool = False
    retrieval_filterable: bool = False
    visible: bool = True
    sort_order: int = 0


class MetadataFieldUpdate(BaseModel):
    name: str | None = None
    options: list[str] | None = None
    default_value: object | None = None
    required: bool | None = None
    filterable: bool | None = None
    retrieval_filterable: bool | None = None
    visible: bool | None = None
    sort_order: int | None = None


class MetadataFieldOut(BaseModel):
    id: str
    kb_id: str
    key: str
    name: str
    scope: str
    data_type: str
    options: list = []
    default_value: object | None = None
    required: bool = False
    filterable: bool = False
    retrieval_filterable: bool = False
    visible: bool = True
    built_in: bool = False
    mapped_field: str | None = None
    sort_order: int = 0
```

Create `backend/app/api/v2/metadata.py`:

```python
router = APIRouter(prefix="/knowledge/{kb_id}/metadata-fields", tags=["metadata"])

@router.get("")
async def list_fields(kb_id: str, scope: str | None = None, me=Depends(get_current_user))

@router.post("", status_code=201)
async def create_field(kb_id: str, body: MetadataFieldCreate, me=Depends(get_current_user))

@router.put("/reorder")
async def reorder_fields(kb_id: str, body: MetadataFieldReorder, me=Depends(get_current_user))

@router.put("/{field_id}")
async def update_field(kb_id: str, field_id: str, body: MetadataFieldUpdate,
                       me=Depends(get_current_user))

@router.delete("/{field_id}")
async def delete_field(kb_id: str, field_id: str, force: bool = False,
                       me=Depends(get_current_user))
```

Use `MetadataFieldReorder(ids: list[str])` to update only `sort_order`. Register the router in `main.py`.

- [ ] **Step 4: Write API integration test**

`backend/tests/test_metadata_api.py` must create an owned KB, then verify:

```python
r = await client.get(f"/api/v2/knowledge/{kb_id}/metadata-fields", headers=H)
assert len(r.json()["data"]) == 6

r = await client.post(f"/api/v2/knowledge/{kb_id}/metadata-fields", headers=H, json={
    "key": "clause_type", "name": "条款类型", "scope": "chunk",
    "data_type": "select", "options": ["义务", "权利"],
    "filterable": True, "retrieval_filterable": True,
})
assert r.json()["code"] == 0
field_id = r.json()["data"]["id"]

r = await client.delete(
    f"/api/v2/knowledge/{kb_id}/metadata-fields/{field_id}?force=true", headers=H
)
assert r.json()["data"] == {"success": True, "affected_count": 0}
```

Also verify a second user receives `FORBIDDEN`, duplicate `scope+key` returns `PARAM_ERROR`, and built-in deletion returns `FORBIDDEN`.

- [ ] **Step 5: Run tests and commit**

```powershell
pytest tests/test_metadata_service.py tests/test_metadata_api.py -v
git add backend/app/services/metadata_service.py backend/app/schemas/knowledge.py backend/app/api/v2/metadata.py backend/app/main.py backend/tests/test_metadata_service.py backend/tests/test_metadata_api.py
git commit -m "feat: add KB metadata schema management"
```

---

### Task 3: Document And Chunk Asset Metadata APIs

**Files:**
- Create: `backend/app/services/asset_service.py`
- Create: `backend/app/api/v2/assets.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/v2/documents.py` only as a compatibility re-export
- Test: `backend/tests/test_asset_metadata_api.py`

- [ ] **Step 1: Write failing integration tests**

Create `backend/tests/test_asset_metadata_api.py` with these exact assertions:

```python
async def test_document_metadata_filter_and_batch_update():
    # Owned KB + two done documents; doc A metadata={"source":"招标文件"},
    # doc B metadata={"source":"投标文件"}
    r = await client.get(
        f"/api/v2/documents?kb_id={kb_id}&document_metadata="
        + quote('{"source":"招标文件"}'),
        headers=H,
    )
    assert [d["name"] for d in r.json()["data"]["list"]] == ["招标文件.pdf"]

    r = await client.post("/api/v2/documents/batch-metadata", headers=H, json={
        "ids": [doc_b_id],
        "metadata": {"source": "招标文件"},
    })
    assert r.json()["data"]["updated"] == 1


async def test_chunk_metadata_and_enabled_filter():
    # One document, chunk A metadata={"effective_status":"现行有效"},
    # chunk B metadata={"effective_status":"已废止"}
    r = await client.patch(
        f"/api/v2/chunks/{chunk_a_id}/metadata", headers=H,
        json={"metadata": {"effective_status": "已废止"}},
    )
    assert r.json()["data"]["metadata"]["effective_status"] == "已废止"

    r = await client.post("/api/v2/chunks/batch-status", headers=H, json={
        "ids": [chunk_b_id], "enabled": False,
    })
    assert r.json()["data"]["updated"] == 1

    r = await client.get(
        f"/api/v2/chunks?kb_id={kb_id}&enabled=false", headers=H
    )
    assert r.json()["data"]["list"][0]["id"] == chunk_b_id
```

Add the same test style for `GET /documents?enabled=false`, document batch status, chunk batch metadata, missing required metadata, unauthorized access, and illegal metadata key rejection.

- [ ] **Step 2: Implement asset list and mutation service**

Create `backend/app/services/asset_service.py`. Its public functions are:

```python
async def list_documents(*, kb_id, user_id, keyword=None, status=None, enabled=None,
                         metadata_filter=None, sort="created_desc", page=1,
                         page_size=20) -> tuple[list[Document], int]
async def list_chunks(*, kb_id, user_id, keyword=None, document_id=None,
                      vector_state=None, enabled=None, metadata_filter=None,
                      page=1, page_size=20) -> tuple[list[Chunk], int]
async def update_document_metadata(doc_id, user_id, metadata) -> Document
async def update_chunk_metadata(chunk_id, user_id, metadata) -> Chunk
async def batch_update_metadata(ids, user_id, scope, metadata) -> int
async def batch_update_status(ids, user_id, scope, enabled) -> int
async def asset_output(asset, scope: str) -> dict
```

Implementation rules:

1. Resolve the KB owner before every mutation.
2. Document metadata validates against enabled document fields; chunk metadata validates against enabled chunk fields.
3. `PATCH` requests contain a complete editable metadata object and call `await validate_metadata(require_complete=True)`; batch requests merge the supplied keys over each row's current object. Built-ins with `mapped_field is not None` are returned for display but stripped before writing because their values live in physical columns; stored built-in `source` remains writable JSON metadata.
4. Sorting supports `created_desc`, `created_asc`, `name_asc`, `name_desc`, `chunk_count_desc`, `recall_count_desc`, `seq_asc`.
5. `vector_state=vectorized` means `Chunk.embedding IS NOT NULL`; `pending` means null.
6. `asset_output` maps ORM objects to snake_case API fields, always includes `metadata`, `enabled`, and `recall_count`, and includes `chunk_count`/`char_count` only for chunks.
7. Pagination uses `offset`/`limit` and a separate count query.
8. `asset_output` composes document `metadata` as virtual physical built-ins plus stored JSON metadata. Example: `document_name` comes from `Document.name`, `upload_date` from `created_at`, and `source` from `metadata_["source"]`. Chunk output has no virtual built-ins in V1.
9. Metadata list filters are schema-validated before querying; unknown keys and non-filterable fields return `PARAM_ERROR`.

- [ ] **Step 3: Consolidate routes**

Move the existing upload, list, detail, and delete document endpoints from `documents.py` into `assets.py`, then update their bodies to call `asset_service`. Make `documents.py` contain only:

```python
from app.api.v2.assets import router  # compatibility for old imports
```

Update `main.py` to include `assets.router`; do not include both routers, because duplicate `/documents` paths would create route-shadowing behavior.

Create `backend/app/api/v2/assets.py`:

```python
@router.get("/documents")
async def list_documents(
    kb_id: str,
    keyword: str | None = None,
    status: str | None = None,
    enabled: bool | None = None,
    document_metadata: str | None = None,
    sort: str = "created_desc",
    page: int = 1,
    page_size: int = 20,
    me=Depends(get_current_user),
)

@router.patch("/documents/{doc_id}/metadata")
async def update_document_metadata(doc_id: str, body: MetadataUpdate,
                                   me=Depends(get_current_user))

@router.post("/documents/batch-metadata")
async def batch_document_metadata(body: BatchMetadata, me=Depends(get_current_user))

@router.post("/documents/batch-status")
async def batch_document_status(body: BatchStatus, me=Depends(get_current_user))

@router.get("/chunks")
async def list_chunks(
    kb_id: str,
    keyword: str | None = None,
    document_id: str | None = None,
    vector_state: Literal["all", "vectorized", "pending"] = "all",
    enabled: bool | None = None,
    chunk_metadata: str | None = None,
    page: int = 1,
    page_size: int = 20,
    me=Depends(get_current_user),
)

@router.patch("/chunks/{chunk_id}/metadata")
async def update_chunk_metadata(chunk_id: str, body: MetadataUpdate,
                                me=Depends(get_current_user))

@router.post("/chunks/batch-metadata")
async def batch_chunk_metadata(body: BatchMetadata, me=Depends(get_current_user))

@router.post("/chunks/batch-status")
async def batch_chunk_status(body: BatchStatus, me=Depends(get_current_user))
```

Define `MetadataUpdate(metadata: dict)`, `BatchMetadata(ids: list[str], metadata: dict)`, and `BatchStatus(ids: list[str], enabled: bool)`. Parse `document_metadata` and `chunk_metadata` with `json.loads`; malformed JSON is `PARAM_ERROR`.

- [ ] **Step 4: Run focused tests and commit**

```powershell
pytest tests/test_asset_metadata_api.py tests/test_documents_api.py -v
git add backend/app/services/asset_service.py backend/app/api/v2/assets.py backend/app/main.py backend/app/api/v2/documents.py backend/tests/test_asset_metadata_api.py backend/tests/test_documents_api.py
git commit -m "feat: manage document and chunk metadata"
```

---

### Task 4: Per-KB Retrieval Settings And Explicit Model Binding

**Files:**
- Create: `backend/app/services/retrieval_settings_service.py`
- Modify: `backend/app/schemas/knowledge.py`
- Create: `backend/app/api/v2/retrieval_settings.py`
- Modify: `backend/app/providers/langchain_factory.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_retrieval_settings_service.py`
- Test: `backend/tests/test_retrieval_settings_api.py`

- [ ] **Step 1: Write failing service and API tests**

Create `backend/tests/test_retrieval_settings_service.py`:

```python
"""Per-KB retrieval settings resolution and validation tests."""
import uuid

import pytest
from sqlalchemy import delete, select

from app.db.session import async_session
from app.exceptions import BizException
from app.models.knowledge_base import KnowledgeBase
from app.models.model_config import ModelConfig
from app.models.user import User
from app.services.retrieval_settings_service import (
    get_effective_settings,
    save_retrieval_settings,
)


async def _admin_id() -> uuid.UUID:
    async with async_session() as s:
        return (await s.execute(select(User))).scalars().first().id


async def _model(name: str, grp: str, dim: int | None = None) -> ModelConfig:
    async with async_session() as s:
        await s.execute(delete(ModelConfig).where(
            ModelConfig.grp == grp, ModelConfig.name == name
        ))
        await s.commit()
        m = ModelConfig(
            grp=grp,
            name=name,
            prov="openai",
            use="retrieval" if grp == "embed" else "rerank",
            url="http://localhost",
            params={} if dim is None else {"dim": dim},
            is_default=False,
            enabled=True,
        )
        s.add(m)
        await s.commit()
        await s.refresh(m)
        return m


@pytest.mark.asyncio
async def test_priority_is_override_kb_scene_then_default():
    user_id = await _admin_id()
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(
            KnowledgeBase.name == "PlanSettingsPriorityKB"
        ))
        await s.commit()
        kb = KnowledgeBase(
            user_id=user_id,
            name="PlanSettingsPriorityKB",
            scene="general",
            retrieval_top_k=7,
            retrieval_config={"vector_top_k": 12, "vector_weight": 0.8},
        )
        s.add(kb)
        await s.commit()
        kb_id = str(kb.id)

    effective = await get_effective_settings(
        kb_id=kb_id,
        override={"vector_top_k": 9},
    )
    assert effective["values"]["vector_top_k"] == {
        "value": 9,
        "source": "override",
    }
    assert effective["values"]["vector_weight"] == {
        "value": 0.8,
        "source": "knowledge_base",
    }
    assert effective["values"]["final_top_k"] == {
        "value": 7,
        "source": "knowledge_base",
    }
    assert effective["values"]["method"]["source"] == "system_default"
    assert effective["resolved"]["vector_weight"] + effective["resolved"]["keyword_weight"] == 1


@pytest.mark.asyncio
async def test_save_rejects_wrong_model_group_dimension_and_weights():
    user_id = await _admin_id()
    embed = await _model("plan_embed_1024", "embed", 1024)
    rerank = await _model("plan_rerank", "rerank")
    llm = await _model("plan_llm", "llm")

    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(
            KnowledgeBase.name == "PlanSettingsValidationKB"
        ))
        await s.commit()
        kb = KnowledgeBase(user_id=user_id, name="PlanSettingsValidationKB", scene="general")
        s.add(kb)
        await s.commit()
        kb_id = str(kb.id)

    saved = await save_retrieval_settings(
        kb_id=kb_id,
        user_id=user_id,
        embedding_model_id=embed.id,
        rerank_model_id=rerank.id,
        retrieval_config={"method": "vector"},
        update_embedding_model=True,
        update_rerank_model=True,
        update_retrieval_config=True,
    )
    assert saved["embedding_model"]["id"] == str(embed.id)
    assert saved["rebuild_required"] is False

    with pytest.raises(BizException):
        await save_retrieval_settings(
            kb_id=kb_id,
            user_id=user_id,
            embedding_model_id=llm.id,
            update_embedding_model=True,
        )

    with pytest.raises(BizException):
        await save_retrieval_settings(
            kb_id=kb_id,
            user_id=user_id,
            embedding_model_id=embed.id,
            retrieval_config={"vector_weight": 0.2, "keyword_weight": 0.5},
            update_embedding_model=True,
            update_retrieval_config=True,
        )
```

Add a third service test for dimension compatibility:

```python
@pytest.mark.asyncio
async def test_save_rejects_incompatible_dimension_before_changing_kb():
    user_id = await _admin_id()
    embed = await _model("plan_embed_before_bad", "embed", 1024)
    bad_dim = await _model("plan_embed_768", "embed", 768)

    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(
            KnowledgeBase.name == "PlanSettingsDimensionKB"
        ))
        await s.commit()
        kb = KnowledgeBase(user_id=user_id, name="PlanSettingsDimensionKB", scene="general")
        s.add(kb)
        await s.commit()
        kb_id = str(kb.id)

    await save_retrieval_settings(
        kb_id=kb_id,
        user_id=user_id,
        embedding_model_id=embed.id,
        update_embedding_model=True,
    )
    with pytest.raises(BizException):
        await save_retrieval_settings(
            kb_id=kb_id,
            user_id=user_id,
            embedding_model_id=bad_dim.id,
            update_embedding_model=True,
        )

    async with async_session() as s:
        saved_kb = await s.get(KnowledgeBase, kb_id)
    assert saved_kb.embedding_model_id == embed.id
```

Add a fourth service test for PATCH-like update semantics on this PUT endpoint:

```python
@pytest.mark.asyncio
async def test_save_supports_omitted_fields_explicit_clear_and_partial_config():
    user_id = await _admin_id()
    embed = await _model("plan_embed_clear_1024", "embed", 1024)
    rerank = await _model("plan_rerank_clear", "rerank")

    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(
            KnowledgeBase.name == "PlanSettingsPatchSemanticsKB"
        ))
        await s.commit()
        kb = KnowledgeBase(user_id=user_id, name="PlanSettingsPatchSemanticsKB", scene="general")
        s.add(kb)
        await s.commit()
        kb_id = str(kb.id)

    await save_retrieval_settings(
        kb_id=kb_id,
        user_id=user_id,
        embedding_model_id=embed.id,
        rerank_model_id=rerank.id,
        retrieval_config={
            "vector_top_k": 12,
            "vector_weight": 0.8,
            "keyword_weight": 0.2,
        },
        update_embedding_model=True,
        update_rerank_model=True,
        update_retrieval_config=True,
    )

    partial = await save_retrieval_settings(
        kb_id=kb_id,
        user_id=user_id,
        retrieval_config={"vector_top_k": 9},
        update_embedding_model=False,
        update_rerank_model=False,
        update_retrieval_config=True,
    )
    assert partial["embedding_model"]["id"] == str(embed.id)
    assert partial["rerank_model"]["id"] == str(rerank.id)
    assert partial["values"]["vector_top_k"]["value"] == 9
    assert partial["values"]["vector_weight"]["value"] == 0.8

    cleared_embed = await save_retrieval_settings(
        kb_id=kb_id,
        user_id=user_id,
        embedding_model_id=None,
        update_embedding_model=True,
        update_rerank_model=False,
        update_retrieval_config=False,
    )
    assert cleared_embed["embedding_model"] is None
    assert cleared_embed["rerank_model"]["id"] == str(rerank.id)

    reset = await save_retrieval_settings(
        kb_id=kb_id,
        user_id=user_id,
        retrieval_config=None,
        update_embedding_model=False,
        update_rerank_model=False,
        update_retrieval_config=True,
    )
    assert reset["values"]["vector_top_k"]["source"] == "system_default"
    assert reset["values"]["vector_weight"]["source"] == "system_default"
    assert reset["rerank_model"]["id"] == str(rerank.id)
```

Create `backend/tests/test_retrieval_settings_api.py`:

```python
"""Retrieval settings API integration tests."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session
from app.main import app
from app.models.knowledge_base import KnowledgeBase
from app.models.model_config import ModelConfig
from app.models.user import User
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token


async def _token() -> str:
    await ensure_admin()
    async with async_session() as s:
        user = (await s.execute(select(User))).scalars().first()
    return create_access_token(user.id)


async def _model(name: str, grp: str, dim: int | None = None) -> ModelConfig:
    async with async_session() as s:
        await s.execute(delete(ModelConfig).where(
            ModelConfig.grp == grp,
            ModelConfig.name == name,
        ))
        await s.commit()
        model = ModelConfig(
            grp=grp,
            name=name,
            prov="openai",
            use="retrieval" if grp == "embed" else "rerank",
            url="http://localhost",
            params={} if dim is None else {"dim": dim},
            is_default=False,
            enabled=True,
        )
        s.add(model)
        await s.commit()
        await s.refresh(model)
        return model


@pytest.mark.asyncio
async def test_retrieval_settings_get_update_clear_and_validation():
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(
            KnowledgeBase.name == "PlanRetrievalSettingsApiKB"
        ))
        await s.commit()

    embed = await _model("plan_api_embed_1024", "embed", 1024)
    bad_dim = await _model("plan_api_embed_768", "embed", 768)
    rerank = await _model("plan_api_rerank", "rerank")
    llm = await _model("plan_api_llm", "llm")

    async with async_session() as s:
        admin = (await s.execute(select(User))).scalars().first()
        other = User(
            username=f"plan_other_{uuid.uuid4().hex[:8]}",
            hashed_password="not-a-login-secret",
            role="user",
        )
        s.add(other)
        kb = KnowledgeBase(
            user_id=admin.id,
            name="PlanRetrievalSettingsApiKB",
            scene="general",
        )
        s.add(kb)
        await s.commit()
        kb_id, other_id = str(kb.id), other.id

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            token = await _token()
            headers = {"Authorization": f"Bearer {token}"}
            base = f"/api/v2/knowledge/{kb_id}/retrieval-settings"

            response = await client.get(base, headers=headers)
            assert response.status_code == 200
            assert response.json()["code"] == 0
            assert response.json()["data"]["values"]["method"]["source"] == "system_default"

            response = await client.put(base, headers=headers, json={
                "embedding_model_id": str(embed.id),
                "rerank_model_id": str(rerank.id),
                "retrieval_config": {
                    "vector_top_k": 12,
                    "vector_weight": 0.8,
                    "keyword_weight": 0.2,
                },
            })
            assert response.json()["code"] == 0

            response = await client.put(base, headers=headers, json={
                "retrieval_config": {"vector_top_k": 9},
            })
            data = response.json()["data"]
            assert data["embedding_model"]["id"] == str(embed.id)
            assert data["rerank_model"]["id"] == str(rerank.id)
            assert data["values"]["vector_top_k"]["value"] == 9
            assert data["values"]["vector_weight"]["value"] == 0.8

            response = await client.put(base, headers=headers, json={
                "embedding_model_id": None,
            })
            data = response.json()["data"]
            assert data["embedding_model"] is None
            assert data["rerank_model"]["id"] == str(rerank.id)
            assert data["values"]["vector_top_k"]["value"] == 9

            response = await client.put(base, headers=headers, json={
                "rerank_model_id": None,
                "retrieval_config": None,
            })
            data = response.json()["data"]
            assert data["rerank_model"] is None
            assert data["values"]["vector_top_k"]["source"] == "system_default"
            assert data["values"]["vector_weight"]["source"] == "system_default"

            invalid_payloads = [
                {"embedding_model_id": str(llm.id)},
                {"embedding_model_id": str(bad_dim.id)},
                {"retrieval_config": {
                    "vector_weight": 0.2,
                    "keyword_weight": 0.5,
                }},
                {"retrieval_config": {"unknown_key": 1}},
            ]
            for payload in invalid_payloads:
                response = await client.put(base, headers=headers, json=payload)
                assert response.json()["code"] != 0

            other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}
            response = await client.get(base, headers=other_headers)
            assert response.json()["code"] != 0
    finally:
        async with async_session() as s:
            await s.execute(delete(KnowledgeBase).where(
                KnowledgeBase.name == "PlanRetrievalSettingsApiKB"
            ))
            await s.execute(delete(ModelConfig).where(ModelConfig.name.like("plan_api_%")))
            await s.execute(delete(User).where(User.id == other_id))
            await s.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend/`:

```powershell
pytest tests/test_retrieval_settings_service.py tests/test_retrieval_settings_api.py -v
```

Expected: service tests fail importing `app.services.retrieval_settings_service`; API tests return `404` before the router is registered.

- [ ] **Step 3: Implement effective settings resolution**

Create `backend/app/services/retrieval_settings_service.py` with:

```python
RETRIEVAL_METHODS = {"vector", "keyword", "hybrid"}

SYSTEM_DEFAULTS = {
    "method": "hybrid",
    "final_top_k": 5,
    "vector_top_k": 20,
    "keyword_top_k": 20,
    "similarity_threshold": 0.0,
    "vector_weight": 0.7,
    "keyword_weight": 0.3,
    "rrf_k": 60,
    "rerank_enabled": True,
    "rerank_top_n": 10,
    "rerank_trigger_threshold": 0.02,
    "navigation_enabled": True,
    "nav_anchor_count": 3,
    "nav_confidence_threshold": 0.15,
}

SCENE_KEY_MAP = {
    "final_top_k": "top_k",
    "keyword_top_k": "trgm_top_k",
    "rerank_trigger_threshold": "rerank_threshold",
}
```

Public functions:

```python
async def get_effective_settings(kb_id: str, user_id=None,
                                 override: dict | None = None) -> dict
async def save_retrieval_settings(*, kb_id: str, user_id,
                                  embedding_model_id=None,
                                  rerank_model_id=None,
                                  retrieval_config=None,
                                  update_embedding_model=False,
                                  update_rerank_model=False,
                                  update_retrieval_config=False) -> dict
def validate_retrieval_config(config: dict, *, partial: bool = True) -> dict
def resolved_values(effective: dict) -> dict
```

`save_retrieval_settings` update semantics:

- An update flag of `False` means the corresponding value is ignored and that field is not changed.
- `update_embedding_model=True` with a non-null ID binds that model; with `None`, it clears the binding.
- `update_rerank_model=True` with a non-null ID binds that model; with `None`, it clears the binding.
- `update_retrieval_config=True` with an object validates the merged config, then saves only the keys supplied in that object. Existing KB override keys not mentioned remain unchanged.
- `update_retrieval_config=True` with `None` resets `KnowledgeBase.retrieval_config` to `{}`.
- `update_retrieval_config=False` leaves the stored config unchanged regardless of the value passed for `retrieval_config`.
- Validate a partial config by merging it over the stored KB config first, then validate the complete override set with `partial=False`. A merged override may legitimately become empty, in which case save `{}`.

Resolution is explicit and field-by-field:

1. `override`
2. `KnowledgeBase.retrieval_config`; `final_top_k` also reads legacy `retrieval_top_k`
3. scene config from `get_scene_config(kb.scene)`, mapped through `SCENE_KEY_MAP`
4. `SYSTEM_DEFAULTS`

The response shape is:

```json
{
  "values": {
    "vector_top_k": {"value": 9, "source": "override"}
  },
  "resolved": {
    "vector_top_k": 9
  },
  "embedding_model": null,
  "rerank_model": null,
  "rebuild_required": false
}
```

Validation rules:

- `method` is one of `RETRIEVAL_METHODS`
- all TopK values are integers `1..100`
- `similarity_threshold` and `rerank_trigger_threshold` are `0..1`
- `nav_confidence_threshold` is `0..1`
- weights are `0..1` and sum to `1` when both are supplied or both resolved
- `vector_weight > 0` for `vector`; `keyword_weight > 0` for `keyword`
- `rerank_top_n <= vector_top_k + keyword_top_k`
- embedding model config must be enabled, `grp="embed"`, and `params.dim` is either absent or exactly `1024`
- rerank model config must be enabled and `grp="rerank"`
- unknown keys are rejected, not silently ignored

`rebuild_required` is true when saving a different enabled embedding model ID and the KB has chunks with non-null embeddings.

- [ ] **Step 4: Refactor provider construction to accept explicit configs**

In `backend/app/providers/langchain_factory.py`, retain the existing public functions and add:

```python
async def build_embeddings_from_config(cfg: ModelConfig) -> Embeddings
async def build_reranker_from_config(cfg: ModelConfig) -> ApiReranker
async def get_model_by_id(model_id, expected_group: str) -> ModelConfig
```

`build_embeddings()` becomes:

```python
cfg = await get_default_model("embed", "retrieval") or await get_default_model("embed")
if not cfg:
    raise BizException(ErrorCode.DEPENDENCY_DOWN, "未配置默认 Embedding 模型，请在设置页配置")
return await build_embeddings_from_config(cfg)
```

Extract the provider branches currently inside `build_embeddings` into a helper that accepts `cfg`; `build_embeddings_from_config` validates `params.dim == 1024` when present. `ApiReranker` receives the decrypted key inside the provider layer only.

- [ ] **Step 5: Add schemas and settings API**

Add:

```python
class RetrievalSettingsUpdate(BaseModel):
    embedding_model_id: str | None = None
    rerank_model_id: str | None = None
    retrieval_config: dict | None = None


class RetrievalSettingsOut(BaseModel):
    values: dict
    resolved: dict
    embedding_model: dict | None
    rerank_model: dict | None
    rebuild_required: bool
```

Create `backend/app/api/v2/retrieval_settings.py`:

```python
router = APIRouter(prefix="/knowledge/{kb_id}/retrieval-settings",
                  tags=["retrieval-settings"])

@router.get("")
async def get_settings(kb_id: str, me=Depends(get_current_user)):
    return ok(await get_effective_settings(kb_id, user_id=me.id))


@router.put("")
async def update_settings(kb_id: str, body: RetrievalSettingsUpdate,
                          me=Depends(get_current_user)):
    return ok(await save_retrieval_settings(
        kb_id=kb_id,
        user_id=me.id,
        embedding_model_id=body.embedding_model_id,
        rerank_model_id=body.rerank_model_id,
        retrieval_config=body.retrieval_config,
        update_embedding_model="embedding_model_id" in body.model_fields_set,
        update_rerank_model="rerank_model_id" in body.model_fields_set,
        update_retrieval_config="retrieval_config" in body.model_fields_set,
    ))
```

The API test must cover GET source labels, successful PUT, forbidden access for another user, invalid model group, invalid dimension, invalid weight sum, and unknown setting key. It must also assert all three null/omission contracts: an omitted field does not change its stored value; `embedding_model_id: null` or `rerank_model_id: null` clears only that binding; `retrieval_config: null` clears all KB overrides; and a supplied object updates only keys present in that object.

- [ ] **Step 6: Run tests and commit**

```powershell
pytest tests/test_retrieval_settings_service.py tests/test_retrieval_settings_api.py -v
git add backend/app/services/retrieval_settings_service.py backend/app/schemas/knowledge.py backend/app/api/v2/retrieval_settings.py backend/app/providers/langchain_factory.py backend/app/main.py backend/tests/test_retrieval_settings_service.py backend/tests/test_retrieval_settings_api.py
git commit -m "feat: add per-KB retrieval settings"
```

---

### Task 5: Metadata-Aware Search And Retrieval Modes

**Files:**
- Create: `backend/app/core/retrieval/metadata_filter.py`
- Modify: `backend/app/core/retrieval/vector_search.py`
- Modify: `backend/app/core/retrieval/fulltext_search.py`
- Modify: `backend/app/core/retrieval/pipeline.py`
- Modify: `backend/app/api/v2/retrieval.py`
- Test: `backend/tests/test_retrieval_search_filters.py`
- Test: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write failing filter tests**

Create `backend/tests/test_retrieval_search_filters.py` with a real PostgreSQL fixture that inserts one KB, two documents, and four chunks:

```text
doc A: source=招标文件, enabled=true
  chunk A1: effective_status=现行有效, enabled=true, embedding=model_1024
  chunk A2: effective_status=已废止, enabled=true, embedding=model_1024
doc B: source=投标文件, enabled=false
  chunk B1: effective_status=现行有效, enabled=true, embedding=model_1024
  chunk B2: effective_status=现行有效, enabled=true, enabled=false
```

Use a query vector identical to all chunk vectors so SQL ordering is deterministic by `id`; use distinct `seq` values and assert by document/metadata when needed.

```python
@pytest.mark.asyncio
async def test_filters_exclude_disabled_assets_and_metadata():
    hits = await vector_search.search(
        q_emb=[0.1] * 1024,
        kb_ids=[kb_id],
        doc_ids=None,
        scope=None,
        top_k=10,
        metadata_filter=MetadataFilter(
            document={"source": ["招标文件"]},
            chunk={"effective_status": ["现行有效"]},
        ),
        embedding_model="plan_embed_1024",
        similarity_threshold=0.0,
    )
    assert {h["document_name"] for h in hits} == {"招标文件.pdf"}
    assert {h["metadata"]["effective_status"] for h in hits} == {"现行有效"}


@pytest.mark.asyncio
async def test_fulltext_uses_same_predicates():
    hits = await fulltext_search.search(
        query="三年质保",
        kb_ids=[kb_id],
        doc_ids=None,
        scope=None,
        top_k=10,
        metadata_filter=MetadataFilter(
            document={"source": ["招标文件"]},
            chunk={"effective_status": ["现行有效"]},
        ),
    )
    assert all(h["document_name"] == "招标文件.pdf" for h in hits)
```

Also assert numeric `gte/lte`, date `gte/lte`, boolean equality, unknown retrieval-filterable key rejection, select value not in options rejection, and raw key interpolation rejection.

- [ ] **Step 2: Implement safe metadata predicate builder**

Create `backend/app/core/retrieval/metadata_filter.py`:

```python
@dataclass(frozen=True)
class MetadataFilter:
    document: dict[str, object] = field(default_factory=dict)
    chunk: dict[str, object] = field(default_factory=dict)


def build_sql_predicates(
    filters: MetadataFilter,
    document_fields: list[KbMetadataField],
    chunk_fields: list[KbMetadataField],
) -> tuple[list[str], dict[str, object]]:
    ...
```

The function loads enabled fields with `retrieval_filterable=True` through a provided schema list, never from raw user input. It emits bind placeholders such as `:doc_meta_0`, not key names. Supported semantics:

- string/select: direct value or list-of-values OR
- boolean: `true` or `false`
- number/date: value for equality, object with `eq/ne/gt/gte/lt/lte`, or both `gte` and `lte`
- lists mean OR for equality; operator objects mean AND
- empty filter returns no predicates
- unknown key, invalid operator, invalid date, invalid boolean, and non-option select values raise `PARAM_ERROR`

Physical mappings for built-in document fields:

```text
document_name -> documents.name
file_size -> documents.size
uploader -> documents.user_id::text
upload_date -> documents.created_at::date::text
last_update_date -> documents.updated_at::date::text
source -> documents.metadata ->> 'source'
```

All custom fields use `jsonb ->> 'key'`; numeric and date casts occur only after schema type validation.

- [ ] **Step 3: Extend vector and fulltext SQL**

Change both search functions to share a `SELECT ... FROM chunks c JOIN documents d` shape:

```sql
SELECT c.id, c.document_id, d.name AS document_name,
       c.content, c.clause_title, c.section_path, c.page_number,
       c.metadata AS metadata, c.char_count, c.embedding_model,
       1 - (c.embedding <=> cast(:emb as vector)) AS vector_score
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.kb_id = ANY(cast(:kb_ids as text[]))
  AND d.enabled
  AND c.enabled
  AND (cast(:doc_ids as uuid[]) IS NULL OR c.document_id = ANY(cast(:doc_ids as uuid[])))
  AND (cast(:scope as uuid[]) IS NULL OR c.id = ANY(cast(:scope as uuid[])))
  AND (cast(:embedding_model as text) IS NULL OR c.embedding_model = cast(:embedding_model as text))
  AND <metadata predicates>
  AND c.embedding IS NOT NULL
ORDER BY c.embedding <=> cast(:emb as vector)
LIMIT :k
```

The fulltext query is the same except it selects `similarity(c.content_search, :q) AS keyword_score`, uses `c.content_search % :q`, orders by keyword score, and does not require an embedding. Keep backward-compatible default values for new parameters so existing tests can be migrated mechanically rather than deleted.

Result dictionaries use:

```python
{
    "id": str(chunk_id),
    "document_id": str(document_id),
    "document_name": document_name,
    "content": content,
    "clause_title": clause_title,
    "section_path": section_path,
    "page_number": page_number,
    "metadata": metadata_object,
    "char_count": char_count,
    "embedding_model": embedding_model,
    "vector_score": float,
    "keyword_score": float,
}
```

Set the unused score to `None`, not `0`, so debug output can distinguish absent channels.

- [ ] **Step 4: Adapt pipeline to modes, explicit models, and filters**

Refactor `RetrievalPipeline` construction to:

```python
class RetrievalPipeline:
    def __init__(self, *, settings: dict, embedding_model=None, rerank_model=None):
        self.settings = resolved_values(settings)
        self.embedding_model = embedding_model
        self.rerank_model = rerank_model
```

`search` signature:

```python
async def search(
    self,
    query: str,
    *,
    kb_ids: list[str] | None = None,
    doc_ids: list[str] | None = None,
    scope: list[str] | None = None,
    metadata_filter: MetadataFilter | None = None,
    top_k: int | None = None,
    enable_nav: bool | None = None,
    count_recall: bool = True,
) -> RetrievalResult
```

Behavior:

1. Resolve settings once; do not silently mix scene defaults during execution.
2. Embed only when method is `vector` or `hybrid`, or navigation is active.
3. Run vector-only, keyword-only, or both according to `method`.
4. For hybrid, fuse with `vector_weight`, `keyword_weight`, and `rrf_k`; single-mode results copy their channel score to `rrf` and set channel rank.
5. Apply similarity threshold to vector candidates before fusion.
6. Navigation still requires `doc_ids`; for KB-only search, skip navigation and preserve hybrid mode.
7. Rerank with the explicit KB rerank config when enabled and triggered. If no explicit rerank model is bound, keep RRF order, set `rerank_triggered=False`, and add `rerank_skipped_reason="rerank_model_not_bound"`. If an explicit model is bound but construction or the provider call fails, propagate the error so a production request or test case can report failure rather than silently falling back.
8. Return the top `final_top_k`.
9. When `count_recall=True`, increment `recall_count` for returned chunk IDs and their document IDs in one SQL statement. Test-run callers pass `False`.

Add `HybridRetriever.from_knowledge_base(kb_id, user_id)` later only when chat integration consumes it; do not add speculative adapters in this task.

- [ ] **Step 5: Update debug `/search` API**

`SearchReq` becomes:

```python
class SearchReq(BaseModel):
    kb_ids: list[str] = []
    document_ids: list[str] = []
    question: str
    top_k: int | None = None
    override_config: dict = {}
    document_metadata: dict = {}
    chunk_metadata: dict = {}
```

When exactly one KB is supplied, resolve its settings and explicit models. With no KB, retain current system-default behavior for backward compatibility. Metadata filters are validated against each selected KB's schema before search.

Extend the existing API test to patch the pipeline boundary and verify method/filter parameters are passed, plus one DB-backed test that disabled documents/chunks do not return.

- [ ] **Step 6: Run tests and commit**

```powershell
pytest tests/test_retrieval_search_filters.py tests/test_pipeline.py tests/test_vector_search.py tests/test_fulltext_search.py tests/test_retrieval_api.py -v
git add backend/app/core/retrieval backend/app/api/v2/retrieval.py backend/tests/test_retrieval_search_filters.py backend/tests/test_pipeline.py
git commit -m "feat: add metadata-aware KB retrieval"
```

---

### Task 6: KB-Bound Embedding And Reindexing

**Files:**
- Modify: `backend/app/worker/app.py`
- Modify: `backend/app/api/v2/assets.py`
- Modify: `backend/app/schemas/knowledge.py`
- Test: `backend/tests/test_reembedding_worker.py`

- [ ] **Step 1: Write failing worker and API tests**

Create `backend/tests/test_reembedding_worker.py` with two real-DB tests.

The first verifies parsing setup:

```python
@pytest.mark.asyncio
async def test_parse_chunks_use_kb_embedding_and_defaults(monkeypatch, tmp_path):
    # Create KB with embedding_model_id pointing to enabled 1024-dim model.
    # Create a pending Document and ParseTask.
    # Mock storage.get to return b"# Terms\nthree-year warranty".
    # Mock build_embeddings_from_config; aembed_documents returns [[0.2] * 1024].
    await parse_document_task({}, str(doc_id))

    async with async_session() as s:
        chunks = (await s.execute(select(Chunk).where(
            Chunk.document_id == doc_id
        ))).scalars().all()
        assert len(chunks) == 1
        assert chunks[0].embedding == [0.2] * 1024
        assert chunks[0].embedding_model == "plan_embed_1024"
        assert chunks[0].char_count == len(chunks[0].content)
        assert chunks[0].metadata_ == {}
```

The second verifies selective reindexing:

```python
@pytest.mark.asyncio
async def test_reembed_only_selected_chunks(monkeypatch):
    # Create one KB, two documents, two vectorized chunks.
    # Change KB embedding_model_id to a second 1024-dim model.
    fake = AsyncMock()
    fake.aembed_documents = AsyncMock(return_value=[[0.9] * 1024])
    monkeypatch.setattr(
        "app.worker.app.build_embeddings_from_config",
        AsyncMock(return_value=fake),
    )
    await reembed_chunks_task({}, str(kb_id), [str(chunk_a_id)])

    async with async_session() as s:
        a = await s.get(Chunk, chunk_a_id)
        b = await s.get(Chunk, chunk_b_id)
    assert a.embedding == [0.9] * 1024
    assert a.embedding_model == "plan_embed_1024_v2"
    assert b.embedding == old_embedding
```

Add an API test that:

1. creates a KB and documents/chunks;
2. patches `app.api.v2.assets.create_pool` to return an `AsyncMock`;
3. posts `{"kb_id": kb_id, "document_ids": [doc_id]}` to `/api/v2/chunks/reembed`;
4. asserts code 0 and `enqueue_job.assert_called_once_with("reembed_chunks_task", kb_id, doc_ids, [])`;
5. verifies another user's KB returns `FORBIDDEN`.

- [ ] **Step 2: Resolve the KB embedding model in the worker**

Refactor `backend/app/worker/app.py`:

```python
async def _kb_embedding_model(kb: KnowledgeBase):
    if kb.embedding_model_id:
        return await get_model_by_id(kb.embedding_model_id, "embed")
    return None
```

During `parse_document_task`:

1. read `kb.embedding_model_id`;
2. call `get_model_by_id` when present, otherwise leave `embedding_model=None`;
3. build embeddings with `build_embeddings_from_config(cfg)` for an explicit model and `build_embeddings()` for the system default;
4. set every chunk's `char_count=len(content)` and `metadata_={}`;
5. write the actual model name (`cfg.name`) into `Chunk.embedding_model`, never the literal `"default"`;
6. preserve the existing retry and status behavior.

If the bound model disappears or is disabled before parsing, the document transitions to `failed` with a readable error such as `知识库绑定的 Embedding 模型不可用`.

- [ ] **Step 3: Add the ARQ reindex task**

In the same worker module:

```python
async def reembed_chunks_task(ctx, kb_id: str, document_ids: list[str], chunk_ids: list[str]):
    ...
```

Implementation:

1. Load the KB once.
2. Resolve its explicit embedding model or system default.
3. Query only chunks joined to that KB, additionally filtered by nonempty `document_ids` and `chunk_ids`.
4. Keep document and chunk `enabled` values unchanged.
5. Embed in batches of 32 or fewer.
6. Update each chunk's `embedding` and `embedding_model` in the same batch transaction.
7. Fail the ARQ job on terminal model errors; no partial status table is introduced in V1.

Register the function:

```python
class WorkerSettings:
    functions = [parse_document_task, reembed_chunks_task]
```

- [ ] **Step 4: Add the reindex API**

In `backend/app/schemas/knowledge.py`:

```python
class ReembedRequest(BaseModel):
    kb_id: str
    document_ids: list[str] = []
    chunk_ids: list[str] = []
```

In `backend/app/api/v2/assets.py`:

```python
@router.post("/chunks/reembed")
async def reembed_chunks(body: ReembedRequest, me=Depends(get_current_user)):
    async with async_session() as s:
        kb = (await s.execute(select(KnowledgeBase).where(
            KnowledgeBase.id == body.kb_id,
            KnowledgeBase.user_id == me.id,
        ))).scalar_one_or_none()
    if not kb:
        raise BizException(ErrorCode.FORBIDDEN, "无权访问该知识库")

    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job(
        "reembed_chunks_task",
        body.kb_id,
        body.document_ids,
        body.chunk_ids,
    )
    return ok({"queued": True})
```

Validate UUID strings before enqueueing; an empty selector means all chunks in the KB.

- [ ] **Step 5: Run tests and commit**

```powershell
pytest tests/test_reembedding_worker.py tests/test_asset_metadata_api.py -v
git add backend/app/worker/app.py backend/app/api/v2/assets.py backend/app/schemas/knowledge.py backend/tests/test_reembedding_worker.py
git commit -m "feat: bind KB embedding to indexing and reindexing"
```

---

### Task 7: Retrieval Test Sets, Cases, And Pure Metrics

**Files:**
- Create: `backend/app/core/retrieval/test_metrics.py`
- Create: `backend/app/schemas/retrieval_testing.py`
- Create: `backend/app/services/retrieval_test_service.py`
- Create: `backend/app/api/v2/retrieval_testing.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_retrieval_test_metrics.py`
- Test: `backend/tests/test_retrieval_testing_api.py`

- [ ] **Step 1: Write failing pure metric tests**

Create `backend/tests/test_retrieval_test_metrics.py`:

```python
"""Pure retrieval quality metric tests."""
import pytest

from app.core.retrieval.test_metrics import (
    aggregate_metrics,
    evaluate_case,
    nearest_rank_percentile,
)


def test_evaluate_case_hit_partial_and_miss():
    result_docs = ["d2", "d1", "d3"]
    assert evaluate_case(["d1"], result_docs, k=3) == {
        "status": "hit",
        "hit_doc_ids": ["d1"],
        "hit_count": 1,
        "recall": 1.0,
        "reciprocal_rank": 0.5,
        "first_hit_rank": 2,
    }
    partial = evaluate_case(["d1", "d4"], result_docs, k=3)
    assert partial["status"] == "partial_hit"
    assert partial["recall"] == 0.5
    miss = evaluate_case(["d4"], result_docs, k=3)
    assert miss["status"] == "miss"
    assert miss["reciprocal_rank"] == 0.0


def test_empty_expected_is_not_evaluated():
    metrics = evaluate_case([], ["d1"], k=3)
    assert metrics == {
        "status": "skipped",
        "hit_doc_ids": [],
        "hit_count": 0,
        "recall": None,
        "reciprocal_rank": None,
        "first_hit_rank": None,
    }


def test_aggregate_multiple_ks_and_latency():
    cases = [
        {"expected_doc_ids": ["d1"], "hit_doc_ids": ["d1"], "status": "hit",
         "recall": 1.0, "reciprocal_rank": 1.0, "latency_ms": 100, "rerank_triggered": True,
         "results": [{"document_id": "d1"}]},
        {"expected_doc_ids": ["d2", "d3"], "hit_doc_ids": ["d2"], "status": "partial_hit",
         "recall": 0.5, "reciprocal_rank": 0.25, "latency_ms": 300, "rerank_triggered": False,
         "results": [{"document_id": "d2"}, {"document_id": "d1"}]},
        {"expected_doc_ids": [], "hit_doc_ids": [], "status": "skipped",
         "recall": None, "reciprocal_rank": None, "latency_ms": 50, "rerank_triggered": False,
         "results": []},
    ]
    metrics = aggregate_metrics(cases, ks=[1, 2])
    assert metrics["case_count"] == 3
    assert metrics["evaluated_case_count"] == 2
    assert metrics["hit_at_k"]["1"] == 0.5
    assert metrics["hit_at_k"]["2"] == 1.0
    assert metrics["recall_at_k"]["2"] == 0.75
    assert metrics["mrr"] == pytest.approx(0.625)
    assert metrics["latency_ms"]["p50"] == 100
    assert metrics["latency_ms"]["p95"] == 300
    assert metrics["rerank_trigger_rate"] == 0.5


def test_nearest_rank_percentile_edge_cases():
    assert nearest_rank_percentile([], 50) is None
    assert nearest_rank_percentile([10, 20, 30, 40], 50) == 30
    assert nearest_rank_percentile([10, 20, 30, 40], 95) == 40
```

- [ ] **Step 2: Implement pure metrics**

`backend/app/core/retrieval/test_metrics.py` contains only pure functions and no DB/import side effects.

```python
def evaluate_case(expected_doc_ids: list[str], result_docs: list[str], *, k: int) -> dict:
    expected = list(dict.fromkeys(map(str, expected_doc_ids)))
    if not expected:
        return {
            "status": "skipped", "hit_doc_ids": [], "hit_count": 0,
            "recall": None, "reciprocal_rank": None, "first_hit_rank": None,
        }
    ranked_docs = [str(doc_id) for doc_id in result_docs[:k]]
    hits = [doc_id for doc_id in expected if doc_id in ranked_docs]
    first_rank = next((ranked_docs.index(doc_id) + 1 for doc_id in hits), None)
    recall = len(hits) / len(expected)
    status = "hit" if len(hits) == len(expected) else "partial_hit" if hits else "miss"
    return {
        "status": status,
        "hit_doc_ids": hits,
        "hit_count": len(hits),
        "recall": recall,
        "reciprocal_rank": 1.0 / first_rank if first_rank else 0.0,
        "first_hit_rank": first_rank,
    }
```

`aggregate_metrics` computes Hit@K and Recall@K from each case's stored `results` documents, uses stored per-case `recall` and `reciprocal_rank` for the configured final K, and returns:

```python
{
    "case_count": int,
    "evaluated_case_count": int,
    "hit_at_k": {str(k): float},
    "recall_at_k": {str(k): float},
    "mrr": float,
    "latency_ms": {"p50": int | None, "p95": int | None},
    "rerank_trigger_rate": float,
    "navigation_scoped_rate": float,
    "failure_rate": float,
}
```

Use nearest-rank percentiles over successful cases only. Zero denominators return `0.0`, while missing latency returns `None`.

- [ ] **Step 3: Add schemas**

`backend/app/schemas/retrieval_testing.py`:

```python
class RetrievalTestSetCreate(BaseModel):
    name: str
    description: str | None = None


class RetrievalTestSetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    archived: bool | None = None


class RetrievalTestCaseCreate(BaseModel):
    query: str
    expected_doc_ids: list[str] = []
    expected_chunk_ids: list[str] = []
    tags: list[str] = []
    enabled: bool = True
    sort_order: int = 0


class RetrievalTestCaseUpdate(BaseModel):
    query: str | None = None
    expected_doc_ids: list[str] | None = None
    expected_chunk_ids: list[str] | None = None
    tags: list[str] | None = None
    enabled: bool | None = None
    sort_order: int | None = None


class TestCaseBatchStatus(BaseModel):
    ids: list[str]
    enabled: bool
```

Response models serialize UUIDs to strings, JSONB arrays/objects unchanged, and timestamps as ISO strings. `expected_chunk_ids` remains visible in V1 API payloads but is excluded from UI forms and metric calculations.

- [ ] **Step 4: Implement set and case CRUD service**

`backend/app/services/retrieval_test_service.py` public functions:

```python
async def list_test_sets(kb_id, user_id, include_archived=False)
async def get_test_set(set_id, user_id)
async def create_test_set(kb_id, user_id, name, description=None)
async def update_test_set(set_id, user_id, **changes)
async def delete_test_set(set_id, user_id)
async def list_cases(test_set_id, user_id, enabled: bool | None = None)
async def create_case(test_set_id, user_id, **fields)
async def update_case(case_id, user_id, **changes)
async def delete_case(case_id, user_id)
async def batch_case_status(ids, user_id, enabled)
async def list_runs(test_set_id, user_id)
```

Every read and mutation joins through `RetrievalTestSet -> KnowledgeBase` and checks `knowledge_bases.user_id`. Expected document IDs must belong to the same KB; `query` cannot be blank; names are limited to 100 characters; tags are deduplicated and limited to 20 entries.

- [ ] **Step 5: Add CRUD API routes**

Create `backend/app/api/v2/retrieval_testing.py`:

```python
@router.get("/knowledge/{kb_id}/retrieval-test-sets")
@router.post("/knowledge/{kb_id}/retrieval-test-sets")
@router.get("/retrieval-test-sets/{set_id}")
@router.put("/retrieval-test-sets/{set_id}")
@router.delete("/retrieval-test-sets/{set_id}")
@router.get("/retrieval-test-sets/{set_id}/cases")
@router.post("/retrieval-test-sets/{set_id}/cases")
@router.put("/retrieval-test-cases/{case_id}")
@router.delete("/retrieval-test-cases/{case_id}")
@router.post("/retrieval-test-cases/batch-status")
@router.get("/retrieval-test-sets/{set_id}/runs")
```

List responses use `{ list, total }`. A case response includes `first_expected_hit_rank`, `status`, `latency_ms`, and `last_run_at` only when joined from run results; CRUD case responses omit those run fields.

- [ ] **Step 6: Write CRUD API integration tests**

`backend/tests/test_retrieval_testing_api.py` must cover:

1. create set, create case, update case, batch disable, list;
2. expected document from another KB is rejected;
3. set and case access by another user returns `FORBIDDEN`;
4. delete set cascades cases in the database;
5. archived sets are hidden by default and returned with `include_archived=true`;
6. run history endpoint returns an empty list initially.

- [ ] **Step 7: Run tests and commit**

```powershell
pytest tests/test_retrieval_test_metrics.py tests/test_retrieval_testing_api.py -v
git add backend/app/core/retrieval/test_metrics.py backend/app/schemas/retrieval_testing.py backend/app/services/retrieval_test_service.py backend/app/api/v2/retrieval_testing.py backend/app/main.py backend/tests/test_retrieval_test_metrics.py backend/tests/test_retrieval_testing_api.py
git commit -m "feat: add saved retrieval test sets"
```

---

### Task 8: Asynchronous Retrieval Test Runs

**Files:**
- Modify: `backend/app/services/retrieval_test_service.py`
- Modify: `backend/app/api/v2/retrieval_testing.py`
- Modify: `backend/app/worker/app.py`
- Test: `backend/tests/test_retrieval_testing_api.py`
- Test: `backend/tests/test_retrieval_test_metrics.py`

- [ ] **Step 1: Verify the one-active-run database constraint**

The Task 1 migration must already contain `uq_retrieval_test_runs_active` as a partial unique index on `test_set_id` where `status IN ('pending', 'running')`. Confirm it exists before adding run code; this protects the single-active-run rule even under concurrent API requests.

- [ ] **Step 2: Extend run service tests**

Add to `backend/tests/test_retrieval_testing_api.py`:

```python
@pytest.mark.asyncio
async def test_start_run_creates_snapshot_and_results(monkeypatch):
    fake_pool = AsyncMock()
    monkeypatch.setattr(
        "app.api.v2.retrieval_testing.create_pool",
        AsyncMock(return_value=fake_pool),
    )
    r = await client.post(
        f"/api/v2/retrieval-test-sets/{set_id}/runs",
        headers=H,
        json={
            "case_ids": [],
            "ks": [3, 5],
            "override_config": {"vector_top_k": 9},
            "document_metadata": {"source": ["招标文件"]},
            "chunk_metadata": {"effective_status": ["现行有效"]},
        },
    )
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "pending"
    assert body["data"]["total_cases"] == 2
    assert body["data"]["config_snapshot"]["settings"]["resolved"]["vector_top_k"] == 9
    assert body["data"]["config_snapshot"]["document_metadata"]["source"] == ["招标文件"]
    fake_pool.enqueue_job.assert_called_once_with(
        "run_retrieval_test_task", body["data"]["id"]
    )
```

Add tests for:

1. empty enabled test set returns `PARAM_ERROR`;
2. invalid `ks`, empty `ks`, or `K > 100` returns `PARAM_ERROR`;
3. duplicate start returns the existing pending run and does not enqueue again;
4. another user cannot start, read, list, or cancel a run;
5. `GET /runs/{run_id}/cases` hides pending internals unless the caller owns the KB;
6. cancel changes `running/pending` to `canceled` and unfinished results to `skipped`.

- [ ] **Step 3: Implement run creation**

In `backend/app/services/retrieval_test_service.py` add:

```python
async def start_run(*, test_set_id, user_id, case_ids=None, ks=None,
                    override_config=None, document_metadata=None,
                    chunk_metadata=None) -> RetrievalTestRun
async def execute_run(run_id: str) -> None
async def get_run(run_id: str, user_id) -> RetrievalTestRun
async def list_run_cases(run_id: str, user_id)
async def cancel_run(run_id: str, user_id) -> RetrievalTestRun
```

`start_run`:

1. loads the set and owning KB;
2. checks for an existing `pending/running` run and returns it unchanged;
3. selects enabled cases, filtered by `case_ids` when supplied;
4. validates `ks` as a nonempty unique integer list in `1..100`;
5. validates `override_config` with `validate_retrieval_config(partial=True)`;
6. validates metadata filters against retrieval-filterable fields;
7. calls `get_effective_settings` with the override;
8. snapshots only safe values:

```python
{
  "settings": effective,
  "ks": sorted(ks),
  "embedding_model": {"id": str, "name": str, "prov": str, "dim": int | None} | None,
  "rerank_model": {"id": str, "name": str, "prov": str} | None,
  "document_metadata": document_metadata,
  "chunk_metadata": chunk_metadata
}
```

9. creates one `pending` case result per selected case;
10. enqueues `run_retrieval_test_task` after the run and results commit.

The snapshot never contains API keys, encrypted values, URLs, or full provider config.

- [ ] **Step 4: Implement the ARQ run task**

Add to `backend/app/worker/app.py`:

```python
async def run_retrieval_test_task(ctx, run_id: str):
    await execute_run(run_id)
```

Register it in `WorkerSettings.functions`.

`execute_run` algorithm:

1. Load the run with `with_for_update(skip_locked=True)`.
2. If status is not `pending`, return immediately.
3. Set `status="running"` and `started_at=utcnow`.
4. Resolve model configs from snapshot IDs and reject disabled/wrong-group configs as terminal errors.
5. Construct `RetrievalPipeline(settings=snapshot["settings"], embedding_model=..., rerank_model=...)`.
6. For each pending result:
   - set result `running`;
   - run pipeline search with `count_recall=False`, KB ID, snapshot metadata filters, and the case query;
   - assign final ranks `1..N`;
   - normalize candidate fields to the spec JSON;
   - compute `evaluate_case` for each K and store per-K metrics;
   - set final case status to the highest-K evaluated status, or `skipped` when expected docs are empty;
   - measure latency around only retrieval plus rerank;
   - on a single-case provider/search error, store the readable error, set `failed`, increment progress, and continue;
7. On terminal model/config errors, mark unfinished results `skipped`, run `failed`, store `error`, and stop.
8. Aggregate all case results with `aggregate_metrics`;
9. set `status="completed"`, `metrics`, and `finished_at`, even if some individual cases failed.
10. Commit progress after each case so frontend polling is useful.

Cancellation wins by checking run status before each case; if it changed to `canceled`, mark only still-pending results as `skipped` and return.

- [ ] **Step 5: Add run routes**

Extend `backend/app/api/v2/retrieval_testing.py`:

```python
class RetrievalRunCreate(BaseModel):
    case_ids: list[str] = []
    ks: list[int] = [3, 5, 10]
    override_config: dict = {}
    document_metadata: dict = {}
    chunk_metadata: dict = {}


@router.post("/retrieval-test-sets/{set_id}/runs")
async def start_run(set_id: str, body: RetrievalRunCreate,
                    me=Depends(get_current_user)):
    ...

@router.get("/retrieval-test-runs/{run_id}")
@router.get("/retrieval-test-runs/{run_id}/cases")
@router.post("/retrieval-test-runs/{run_id}/cancel")
```

`GET run` returns:

```python
{
    "id": str,
    "test_set_id": str,
    "kb_id": str,
    "status": str,
    "config_snapshot": dict,
    "override_config": dict,
    "total_cases": int,
    "completed_cases": int,
    "metrics": dict,
    "error": str | None,
    "started_at": str | None,
    "finished_at": str | None,
    "created_at": str,
}
```

- [ ] **Step 6: Add execution test with mocked pipeline**

Patch `RetrievalPipeline.search` in the worker module and verify:

1. two successful cases produce `hit` and `miss`;
2. `count_recall=False` is passed;
3. run metrics aggregate correctly;
4. a raised rerank error marks that case `failed`, continues the second case, and completes the run;
5. an unavailable embedding model marks the run `failed` and all unexecuted cases `skipped`;
6. document/chunk `recall_count` values remain unchanged.

Use distinct returned document IDs to verify final ranks, vector/keyword ranks, RRF score, and rerank score are persisted in candidate `results`.

- [ ] **Step 7: Run tests and commit**

```powershell
pytest tests/test_retrieval_testing_api.py tests/test_retrieval_test_metrics.py -v
git add backend/app/services/retrieval_test_service.py backend/app/api/v2/retrieval_testing.py backend/app/worker/app.py backend/tests/test_retrieval_testing_api.py backend/tests/test_retrieval_test_metrics.py
git commit -m "feat: run asynchronous retrieval regression tests"
```

---

### Task 9: Frontend Contracts, Mock, And Store

**Files:**
- Modify: `frontend/src/types/knowledge.ts`
- Modify: `frontend/src/api/knowledge.ts`
- Modify: `frontend/src/mock/knowledge.ts`
- Modify: `frontend/src/mock/index.ts`
- Modify: `frontend/src/stores/knowledge.ts`
- Test: `cd frontend && npm run build`

Do not add a frontend dependency. Continue using Axios, Pinia, TypeScript, and the existing request/mock adapter.

- [ ] **Step 1: Define final snake-case API types**

Add these contracts to `frontend/src/types/knowledge.ts`:

```ts
export type MetadataScope = 'document' | 'chunk'
export type MetadataDataType = 'string' | 'number' | 'date' | 'select' | 'boolean'
export type RetrievalMethod = 'vector' | 'keyword' | 'hybrid'
export type TestRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'canceled'
export type TestCaseStatus =
  | 'pending' | 'running' | 'hit' | 'partial_hit' | 'miss' | 'failed' | 'skipped'

export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  scene: string
  cover: string | null
  doc_count: number
  total_size: number
  chunk_count: number
  last_test_at: string | null
  created_at: string
}

export interface MetadataField {
  id: string
  kb_id: string
  key: string
  name: string
  scope: MetadataScope
  data_type: MetadataDataType
  options: string[]
  default_value: unknown
  required: boolean
  filterable: boolean
  retrieval_filterable: boolean
  visible: boolean
  built_in: boolean
  mapped_field: string | null
  sort_order: number
}

export interface DocumentAsset {
  id: string
  kb_id: string
  name: string
  ext: string
  size: number
  pages: number
  mode: 'fast' | 'precision'
  status: 'pending' | 'parsing' | 'done' | 'failed'
  pct: number
  element_count: number
  chunk_count: number
  metadata: Record<string, unknown>
  enabled: boolean
  recall_count: number
  created_at: string
}

export interface ChunkAsset {
  id: string
  kb_id: string
  document_id: string
  document_name: string
  content: string
  content_search: string | null
  clause_title: string | null
  section_path: string | null
  page_number: number
  seq: number
  char_count: number
  embedding_model: string | null
  metadata: Record<string, unknown>
  enabled: boolean
  recall_count: number
  created_at: string
}

export interface ConfigSource {
  value: string | number | boolean
  source: 'override' | 'knowledge_base' | 'scene' | 'system_default'
}

export interface RetrievalSettings {
  values: Record<string, ConfigSource>
  resolved: Record<string, string | number | boolean>
  embedding_model: { id: string; name: string; prov: string; params: Record<string, unknown> } | null
  rerank_model: { id: string; name: string; prov: string } | null
  rebuild_required: boolean
}

export interface RetrievalTestSet {
  id: string
  kb_id: string
  name: string
  description: string | null
  archived: boolean
  case_count: number
  last_run_at: string | null
  last_metrics: Record<string, Record<string, number | null>> | null
  created_at: string
  updated_at: string
}

export interface RetrievalTestCase {
  id: string
  test_set_id: string
  query: string
  expected_doc_ids: string[]
  expected_chunk_ids: string[]
  tags: string[]
  enabled: boolean
  sort_order: number
  first_expected_hit_rank?: number | null
  status?: TestCaseStatus
  latency_ms?: number | null
  last_run_at?: string | null
  created_at: string
  updated_at: string
}

export interface RetrievalCandidate {
  rank: number
  chunk_id: string
  document_id: string
  document_name: string
  section_path: string | null
  page_number: number
  char_count: number
  vector_score: number | null
  keyword_score: number | null
  vector_rank: number | null
  keyword_rank: number | null
  rrf_score: number | null
  rerank_score: number | null
  metadata: Record<string, unknown>
}

export interface RetrievalTestCaseResult extends RetrievalTestCase {
  run_id: string
  hit_doc_ids: string[]
  results: RetrievalCandidate[]
  metrics: Record<string, unknown>
  error: string | null
}

export interface RetrievalTestRun {
  id: string
  test_set_id: string
  kb_id: string
  status: TestRunStatus
  config_snapshot: {
    settings: RetrievalSettings
    ks: number[]
    embedding_model: { id: string; name: string; prov: string; dim?: number | null } | null
    rerank_model: { id: string; name: string; prov: string } | null
    document_metadata: Record<string, unknown>
    chunk_metadata: Record<string, unknown>
  }
  override_config: Record<string, unknown>
  total_cases: number
  completed_cases: number
  metrics: Record<string, Record<string, number | null> | number | null>
  error: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}
```

Do not map metadata values to `string`; preserve JSON types. Keep the existing `TreeNode`, `DocElement`, and `ParseTask` types. During this task, retain temporary compatibility aliases for the legacy knowledge/detail page, then remove them in Task 10.

- [ ] **Step 2: Add API functions**

Extend `frontend/src/api/knowledge.ts`:

```ts
export function getMetadataFields(kbId: string, scope?: MetadataScope) {
  return request.get(`/knowledge/${kbId}/metadata-fields`, { params: { scope } })
}

export function createMetadataField(kbId: string, data: Omit<MetadataField,
  'id' | 'kb_id' | 'built_in' | 'mapped_field'>) {
  return request.post(`/knowledge/${kbId}/metadata-fields`, data)
}

export function updateMetadataField(kbId: string, id: string, data: Partial<MetadataField>) {
  return request.put(`/knowledge/${kbId}/metadata-fields/${id}`, data)
}

export function deleteMetadataField(kbId: string, id: string, force: boolean) {
  return request.delete(`/knowledge/${kbId}/metadata-fields/${id}`, { params: { force } })
}

export function updateDocumentMetadata(id: string, metadata: Record<string, unknown>) {
  return request.patch(`/documents/${id}/metadata`, { metadata })
}

export function batchUpdateDocumentMetadata(ids: string[], metadata: Record<string, unknown>) {
  return request.post('/documents/batch-metadata', { ids, metadata })
}

export function updateDocumentStatus(ids: string[], enabled: boolean) {
  return request.post('/documents/batch-status', { ids, enabled })
}

export function getChunkList(params: Record<string, unknown>) {
  return request.get('/chunks', { params })
}

export function updateChunkMetadata(id: string, metadata: Record<string, unknown>) {
  return request.patch(`/chunks/${id}/metadata`, { metadata })
}

export function updateChunkStatus(ids: string[], enabled: boolean) {
  return request.post('/chunks/batch-status', { ids, enabled })
}

export function reembedChunks(kbId: string, documentIds: string[], chunkIds: string[]) {
  return request.post('/chunks/reembed', {
    kb_id: kbId, document_ids: documentIds, chunk_ids: chunkIds
  })
}
```

Add the same style for retrieval settings, test sets, cases, runs, cancellation, and run case results. All functions declare concrete return types, no `any`.

- [ ] **Step 3: Build complete mutable Mock data**

Refactor `frontend/src/mock/knowledge.ts` into an in-memory state module:

```ts
export const mockKbs: KnowledgeBase[] = [...]
export const mockDocuments: DocumentAsset[] = [...]
export const mockChunks: ChunkAsset[] = [...]
export const mockMetadataFields: MetadataField[] = [...]
export const mockTestSets: RetrievalTestSet[] = [...]
export const mockTestCases: RetrievalTestCase[] = [...]
export const mockTestRuns: RetrievalTestRun[] = [...]
export const mockTestCaseResults: RetrievalTestCaseResult[] = [...]
export function handleKnowledgeMock(
  url: string,
  method: string,
  data: Record<string, unknown>
): unknown | null
```

Mock contract requirements:

1. Six built-in document fields, including stored `source`, plus chunk fields `clause_type`, `effective_status`, `effective_date`.
2. At least 8 chunks across 3 documents, including disabled and non-vectorized examples.
3. At least 2 test sets, one archived and one active with 5 cases.
4. One completed run with metrics and candidate details, one canceled run.
5. POST/PUT/DELETE mutate the arrays; list endpoints apply keyword/status/metadata/enabled/tag filters and return `{ list, total }`.
6. Metadata field deletion follows the same `force` impact behavior as the backend.
7. POST run creates a pending run plus pending case results; each GET advances `completed_cases` by one and eventually sets `completed` and metrics, allowing polling without timers.
8. All URLs are parsed before the generic `url.includes('/knowledge')` branch.

Do not use browser APIs in mock helpers. Return rejected-shaped `{ code: 40001, message, data: null }` objects for validation failures.

- [ ] **Step 4: Dispatch knowledge mocks before broad fallback**

In `frontend/src/mock/index.ts`, call the specialized handler before the current knowledge/documents branches:

```ts
const knowledgeMock = handleKnowledgeMock(url, method, requestData)
if (knowledgeMock !== null) {
  return knowledgeMock
}
```

Remove URL matching that accidentally captures:

- `/knowledge/{id}/metadata-fields`
- `/knowledge/{id}/retrieval-settings`
- `/knowledge/{id}/retrieval-test-sets`
- `/retrieval-test-sets/{id}`
- `/retrieval-test-runs/{id}`
- `/chunks`

Keep unrelated module mocks unchanged.

- [ ] **Step 5: Extend the Pinia store**

Add state:

```ts
const metadataFields = ref<MetadataField[]>([])
const chunkList = ref<ChunkAsset[]>([])
const chunkTotal = ref(0)
const chunkLoading = ref(false)
const retrievalSettings = ref<RetrievalSettings | null>(null)
const testSets = ref<RetrievalTestSet[]>([])
const currentTestSet = ref<RetrievalTestSet | null>(null)
const testCases = ref<RetrievalTestCase[]>([])
const currentRun = ref<RetrievalTestRun | null>(null)
const runResults = ref<RetrievalTestCaseResult[]>([])
const activeTab = ref<'documents' | 'segments' | 'metadata' | 'testing' | 'settings'>('documents')
const documentFilter = ref<Record<string, unknown>>({})
const chunkFilter = ref<Record<string, unknown>>({})
```

Add actions with explicit return types:

```ts
loadMetadataFields(kbId, scope?)
saveMetadataField(kbId, payload, id?)
removeMetadataField(kbId, id, force)
loadChunks(kbId, filter)
saveDocumentMetadata(ids, metadata)
setDocumentEnabled(ids, enabled)
saveChunkMetadata(ids, metadata)
setChunkEnabled(ids, enabled)
queueReembedding(kbId, documentIds, chunkIds)
loadRetrievalSettings(kbId)
saveRetrievalSettings(kbId, payload)
loadTestSets(kbId, includeArchived?)
saveTestSet(kbId, payload, setId?)
removeTestSet(setId)
loadTestCases(setId)
saveTestCase(setId, payload, caseId?)
removeTestCase(caseId)
setTestCaseEnabled(ids, enabled)
startTestRun(setId, payload)
pollTestRun(runId)
cancelTestRun(runId)
loadRunResults(runId)
```

`pollTestRun` uses a local interval handle in the store, clears it on terminal status and store reset, and never starts a second interval for the same run.

- [ ] **Step 6: Verify contracts and commit**

```powershell
npm run build
git add src/types/knowledge.ts src/api/knowledge.ts src/mock/knowledge.ts src/mock/index.ts src/stores/knowledge.ts
git commit -m "feat: add knowledge management frontend contracts"
```

---

### Task 10: Five-Tab Knowledge Detail Experience

**Files:**
- Modify: `frontend/src/views/knowledge/KbDetailView.vue`
- Create: `frontend/src/views/knowledge/components/DocumentsTab.vue`
- Create: `frontend/src/views/knowledge/components/SegmentsTab.vue`
- Create: `frontend/src/views/knowledge/components/MetadataTab.vue`
- Create: `frontend/src/views/knowledge/components/RetrievalSettingsTab.vue`
- Create: `frontend/src/views/knowledge/components/MetadataEditor.vue`
- Create: `frontend/src/views/knowledge/components/MetadataFieldDialog.vue`
- Modify: `frontend/src/views/knowledge/components/DocumentTable.vue`
- Test: `cd frontend && npm run build`

Use only Element Plus components and the project's existing Element Plus icon strategy. Do not add explanatory marketing text inside the UI.

- [ ] **Step 1: Build the detail shell**

`KbDetailView.vue`:

1. keeps route `/knowledge/:kbId`;
2. loads KB, metadata fields, and documents once;
3. renders sticky `PageHeader` with name, description, document count, chunk count, and latest test time;
4. provides `上传文档` and `运行测试` primary actions;
5. uses `el-tabs` for `文档 / 分段 / 元数据 / 召回测试 / 设置`;
6. restores the active tab from `route.query.tab`, updating the query without reloading data;
7. lazily renders only the active tab;
8. reloads all dependent state when `kbId` changes and resets polling.

Shell template:

```vue
<div class="kb-detail-view">
  <PageHeader :title="currentKb?.name || '知识库详情'">
    <template #subtitle>...</template>
    <template #actions>...</template>
  </PageHeader>
  <el-tabs v-model="activeTab" class="kb-tabs">
    <el-tab-pane label="文档" name="documents">
      <DocumentsTab v-if="activeTab === 'documents'" :kb-id="kbId" />
    </el-tab-pane>
    <el-tab-pane label="分段" name="segments">
      <SegmentsTab v-if="activeTab === 'segments'" :kb-id="kbId" />
    </el-tab-pane>
    <el-tab-pane label="元数据" name="metadata">
      <MetadataTab v-if="activeTab === 'metadata'" :kb-id="kbId" />
    </el-tab-pane>
    <el-tab-pane label="召回测试" name="testing">
      <RetrievalTestingTab v-if="activeTab === 'testing'" :kb-id="kbId" />
    </el-tab-pane>
    <el-tab-pane label="设置" name="settings">
      <RetrievalSettingsTab v-if="activeTab === 'settings'" :kb-id="kbId" />
    </el-tab-pane>
  </el-tabs>
</div>
```

- [ ] **Step 2: Upgrade the documents tab**

`DocumentsTab.vue` contains:

- keyword search with debounced input and search icon button
- status segmented control: `全部 / 等待中 / 解析中 / 已完成 / 失败`
- enabled switch filter: `全部 / 启用 / 禁用`
- dynamic metadata selects generated from `filterable && visible` document fields
- sort select for upload time, name, chunk count, recall count
- batch toolbar visible when rows are selected
- upload panel retained above the table

`DocumentTable.vue` gains stable columns:

```text
selection | 文件 | 大小 | 状态 | 分段数 | 元数据 | 召回次数 | 启用 | 上传时间 | 操作
```

Actions are icon buttons with tooltips: detail, metadata, rebuild index, enable/disable, delete. Required missing metadata is a small red tag on the metadata cell, not a red full row. Batch metadata opens `MetadataEditor`; batch enable and disable use `ElMessageBox.confirm`; delete uses `ConfirmDelete`.

- [ ] **Step 3: Build the segments tab**

`SegmentsTab.vue` has a two-column layout:

```text
left 240px: document list with search, count, and selection
right: filters + chunk table + detail drawer
```

Filters:

- content keyword
- vector state segmented control: `全部 / 已向量化 / 未向量化`
- enabled state segmented control
- dynamic chunk metadata filters

Table columns:

```text
selection | 摘要 | 文档 | 章节 | 页码 | 元数据 | 字符数 | 向量模型 | 召回次数 | 启用 | 操作
```

The detail drawer shows original content, location, quality fields, complete chunk metadata, and hit-history entry text. The metadata edit button opens `MetadataEditor(scope="chunk")`. Batch actions support metadata, enable/disable, and rebuild vectors. Do not provide direct content editing.

- [ ] **Step 4: Build metadata schema management**

`MetadataTab.vue` uses a scope segmented control (`文档 / 分段`) and one table:

```text
排序 | 显示名 | key | 类型 | 必填 | 列表筛选 | 检索过滤 | 默认展示 | 启用 | 操作
```

Rules:

- built-in rows show `内置` tag and cannot delete/change key/type/scope;
- custom rows support edit and delete;
- delete calls with `force=false`; when response `success=false`, show a confirm dialog containing `affected_count`;
- changing retrieval filtering or select options saves immediately after confirmation;
- drag sorting calls the reorder endpoint.

`MetadataFieldDialog.vue` is one create/edit dialog shared by both scopes. It renders type-specific controls:

- text: max length input
- number: min/max inputs stored in `default_value`
- date: date picker
- select: option tag editor
- boolean: switch

The dialog validates key format, duplicate key, select options, and required name before submit.

`MetadataEditor.vue` dynamically renders inputs from enabled visible fields. It supports single and batch modes. In single mode, required fields start with current values; in batch mode, unchanged fields are rendered as empty and only nonempty values are submitted for merge. Select fields use multi-select only when the backend filter accepts arrays; metadata editing uses single values.

- [ ] **Step 5: Build retrieval settings tab**

`RetrievalSettingsTab.vue` uses grouped sections:

```text
索引模型 | 检索策略 | Rerank | 结构导航 | 风险操作
```

Controls:

- embedding model select filtered to enabled 1024-dim models
- rerank model select filtered to enabled rerank models
- retrieval method radio group
- final/vector/keyword TopK numeric inputs
- score threshold slider
- vector/keyword weight sliders that move together and always sum to 1
- RRF K numeric input
- rerank switch/model/candidate count/trigger threshold
- navigation switch/anchor count/confidence threshold

Every field label can expand to show its source tag: `测试覆盖 / 知识库 / 场景 / 系统默认`. Save validates ranges and weight sum client-side, then sends only changed values. Switching embedding to a different model shows a rebuild-required dialog and offers `保存并重建向量`. Risk actions include rebuilding all vectors; changing chunk size/overlap is read-only in V1 and links to the existing KB form.

- [ ] **Step 6: Verify frontend acceptance**

Run:

```powershell
npm run build
```

Manual Mock verification:

1. five tabs persist through refresh via `?tab=`;
2. document metadata filter changes list content;
3. batch metadata edits update visible tags;
4. disabled documents/chunks remain filterable;
5. segment drawer edits chunk metadata;
6. built-in metadata fields are protected;
7. custom field deletion requires force when values exist;
8. settings source labels update after save;
9. no text overflows at 1366px and 375px widths.

- [ ] **Step 7: Commit**

```powershell
git add src/views/knowledge
git commit -m "feat: build knowledge management detail tabs"
```

---

### Task 11: Retrieval Testing Workbench

**Files:**
- Create: `frontend/src/views/knowledge/components/RetrievalTestingTab.vue`
- Create: `frontend/src/views/knowledge/components/TestSetList.vue`
- Create: `frontend/src/views/knowledge/components/TestCaseTable.vue`
- Create: `frontend/src/views/knowledge/components/TestRunPanel.vue`
- Create: `frontend/src/views/knowledge/components/TestCaseDialog.vue`
- Create: `frontend/src/views/knowledge/components/CandidateDetailDrawer.vue`
- Modify: `frontend/src/stores/knowledge.ts`
- Test: `cd frontend && npm run build`

- [ ] **Step 1: Build test set navigation**

`RetrievalTestingTab.vue` uses a two-column workbench:

```text
left 280px: test set list + create button
right: toolbar, case table, metrics, run details
```

`TestSetList.vue` cards show:

- name
- enabled case count
- latest Hit@K
- latest MRR
- last run time
- status tag: active/archived

Actions per card: open, edit, archive/restore, delete. The list defaults to active sets and has an `包含归档` switch. Creating a set opens a small dialog with name and description only.

- [ ] **Step 2: Build case management**

`TestCaseTable.vue` toolbar contains:

- query keyword search
- tag filter
- status filter: `全部 / 启用 / 禁用`
- new case button
- batch enable/disable
- run selected button
- run all button

Columns:

```text
selection | 查询 | 期望文档 | 标签 | 最近状态 | 首个命中排名 | 耗时 | 启用 | 操作
```

`TestCaseDialog.vue` fields:

- query textarea, required
- expected documents multi-select using enabled document list
- tags input
- enabled switch
- sort number

Expected documents are grouped by document name and show file type icons. `expected_chunk_ids` is intentionally absent from the form. A case cannot be saved with a blank query; empty expected documents are allowed and displayed as `未标注`, but such cases are excluded from quality metrics and marked `skipped`.

- [ ] **Step 3: Build run controls and metrics**

`TestRunPanel.vue` has two states.

Idle/configured state:

- selected case count
- K checkboxes for `3 / 5 / 10`
- metadata filter summary button opening a filter drawer
- collapsible override config form
- primary `运行测试` button
- latest completed run summary

Running state:

- status chip
- progress bar using `completed_cases / total_cases`
- cancel button
- current query text
- auto-refresh every 2 seconds

Metrics cards:

```text
Hit@K | Recall@K | MRR | P50 | P95 | Rerank触发率
```

For Hit@K and Recall@K render one value chip per selected K. Use fixed-height metric cards so status changes do not shift layout.

Failure banner appears only when `run.error` or `run.status === 'failed'`. Individual failed case rows show an error icon button that opens the candidate drawer's error section.

- [ ] **Step 4: Build result and configuration details**

The right panel uses inner tabs:

```text
用例结果 | 命中明细 | 生效配置
```

`用例结果` reuses `TestCaseTable` with run-result rows and filters `全部 / 命中 / 部分命中 / 未命中 / 失败 / 跳过`.

`命中明细` lists candidates for the selected case:

```text
rank | 文档 | 章节 | 页码 | 向量分 | 关键词分 | RRF | Rerank | 命中
```

Clicking a row opens `CandidateDetailDrawer.vue`, which shows content preview, metadata, all scores/ranks, and the expected-document highlight.

`生效配置` renders the saved snapshot with source tags:

```text
测试覆盖 / 知识库 / 场景 / 系统默认
```

It also shows embedding model, rerank model, selected K values, and metadata filters. It must render the exact snapshot even after KB settings change.

- [ ] **Step 5: Wire polling and cancellation safely**

In `RetrievalTestingTab.vue`:

1. start polling after POST run succeeds;
2. stop polling on `completed/failed/canceled`, route change, tab change, KB change, and component unmount;
3. disable run buttons while a test set has an active run;
4. after completion, load run results and refresh test set summary;
5. cancellation asks for confirmation, cancels, then polls once immediately.

Manual polling verification: switch tabs during a running Mock run, return to the testing tab, and confirm no duplicate interval is created; then navigate to another KB and confirm the previous run stops polling.

- [ ] **Step 6: Verify and commit**

```powershell
npm run build
git add src/views/knowledge/components/RetrievalTestingTab.vue src/views/knowledge/components/TestSetList.vue src/views/knowledge/components/TestCaseTable.vue src/views/knowledge/components/TestRunPanel.vue src/views/knowledge/components/TestCaseDialog.vue src/views/knowledge/components/CandidateDetailDrawer.vue src/stores/knowledge.ts
git commit -m "feat: build retrieval testing workbench"
```

---

### Task 12: Full Verification And Documentation Sync

**Files:**
- Modify: `docs/frontend-plans/03-knowledge-base.md`
- Modify: `docs/superpowers/specs/2026-08-17-knowledge-base-metadata-retrieval-testing-design.md`
- Test: backend full suite
- Test: frontend build

- [ ] **Step 1: Run backend regression suite**

From `backend/`:

```powershell
pytest -v
alembic upgrade head
```

Required checks:

1. all existing model, parsing, retrieval, settings, knowledge, and document tests pass;
2. no test mutates production-like data outside uniquely named test records;
3. no API response includes `api_key_enc` or a decrypted key;
4. metadata SQL predicates contain only bound parameters;
5. test-run helper calls all pass `count_recall=False`;
6. the one-active-run index exists after migration.

- [ ] **Step 2: Run frontend verification**

From `frontend/`:

```powershell
npm run build
```

Then with `VITE_USE_MOCK=true`:

1. create a custom document field and chunk field;
2. assign metadata to one document and two chunks;
3. filter both lists by metadata;
4. disable one document and one chunk;
5. edit retrieval settings and confirm source labels;
6. create a test set and five cases;
7. run selected cases with override TopK;
8. inspect metrics, candidate details, and configuration snapshot;
9. cancel a Mock running run;
10. refresh each tab URL directly and verify state loads.

- [ ] **Step 3: Synchronize module documentation**

Update `docs/frontend-plans/03-knowledge-base.md`:

- replace the old three-level page description with the five-tab structure;
- add the new component table;
- add document/chunk metadata and retrieval testing interfaces;
- update store, Mock, routing, acceptance checklist, and manual verification items.

Update the spec status section only if implementation reveals an approved deviation. Record deviations as explicit subsections with reason and migration impact; do not silently rewrite accepted requirements.

- [ ] **Step 4: Check plan completion**

Confirm every checkbox in this plan is checked and every task commit exists:

```powershell
git log --oneline --decorate -12
rg -n "\[ \]" docs/superpowers/plans/2026-08-17-kb-metadata-retrieval-testing.md
```

The second command must return no matches.

- [ ] **Step 5: Final commit**

```powershell
git add docs/frontend-plans/03-knowledge-base.md docs/superpowers/specs/2026-08-17-knowledge-base-metadata-retrieval-testing-design.md
git commit -m "docs: update knowledge management implementation docs"
```

If the spec required no edits, commit only the frontend module plan.

---

## Plan Self-Review Checklist

- [ ] Every requirement in spec sections 3-13 maps to a task above.
- [ ] ORM uses `metadata_` while API/database fields remain `metadata`.
- [ ] All frontend contracts use the exact backend snake_case field names.
- [ ] V1 does not expose chunk-level expected hit editing.
- [ ] Retrieval tests never increment recall counts.
- [ ] Vectors remain fixed at 1024 dimensions and incompatible models are rejected.
- [ ] No API key, encrypted key, provider URL, or full provider configuration appears in a run snapshot.
- [ ] Metadata predicates are schema-validated and parameter-bound.
- [ ] Each backend task has failing tests, implementation, focused commands, and commit instructions.
- [ ] Each frontend task has Mock behavior, build verification, and manual acceptance checks.

---

"""Request and response schemas for retrieval testing."""
from pydantic import BaseModel, Field


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
    ids: list[str] = Field(min_length=1)
    enabled: bool


class RetrievalTestSetOut(BaseModel):
    id: str
    kb_id: str
    name: str
    description: str | None
    archived: bool
    created_at: str
    updated_at: str


class RetrievalTestCaseOut(BaseModel):
    id: str
    test_set_id: str
    query: str
    expected_doc_ids: list[str]
    expected_chunk_ids: list[str]
    tags: list[str]
    enabled: bool
    sort_order: int
    created_at: str
    updated_at: str


class RetrievalTestRunOut(BaseModel):
    id: str
    test_set_id: str
    kb_id: str
    status: str
    config_snapshot: dict
    override_config: dict
    total_cases: int
    completed_cases: int
    metrics: dict
    error: str | None
    started_at: str | None
    finished_at: str | None
    created_at: str

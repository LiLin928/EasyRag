"""Metadata-aware vector/fulltext retrieval tests."""

import pytest
from sqlalchemy import delete

from app.core.retrieval import fulltext_search, vector_search
from app.core.retrieval.metadata_filter import MetadataFilter, build_sql_predicates
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.metadata import KbMetadataField
from app.models.user import User
from app.security.init_admin import ensure_admin


def _field(
    key: str,
    scope: str,
    data_type: str,
    *,
    retrieval_filterable: bool = True,
    options: list | None = None,
    mapped_field: str | None = None,
    built_in: bool = False,
) -> KbMetadataField:
    return KbMetadataField(
        key=key,
        name=key,
        scope=scope,
        data_type=data_type,
        options=options or [],
        retrieval_filterable=retrieval_filterable,
        mapped_field=mapped_field,
        built_in=built_in,
    )


def test_empty_filter_has_no_predicates():
    predicates, params = build_sql_predicates(MetadataFilter(), [], [])

    assert predicates == []
    assert params == {}


def test_string_and_select_filters_use_bound_values():
    source = _field("source", "document", "string", mapped_field=None, built_in=True)
    status = _field(
        "effective_status", "chunk", "select", options=["现行有效", "已废止"]
    )

    predicates, params = build_sql_predicates(
        MetadataFilter(
            document={"source": ["招标文件", "内部文件"]},
            chunk={"effective_status": "现行有效"},
        ),
        [source],
        [status],
    )

    joined = " AND ".join(predicates)
    assert "source" not in joined
    assert "effective_status" not in joined
    assert all(":" in predicate for predicate in predicates)
    assert set(params) == {
        "doc_key_0",
        "doc_value_0",
        "chunk_key_0",
        "chunk_value_0",
    }
    assert params["doc_key_0"] == "source"
    assert params["doc_value_0"] == ["招标文件", "内部文件"]
    assert params["chunk_key_0"] == "effective_status"
    assert params["chunk_value_0"] == "现行有效"


def test_number_date_and_boolean_operator_semantics():
    file_size = _field("file_size", "document", "number", mapped_field="size", built_in=True)
    upload_date = _field(
        "upload_date", "document", "date", mapped_field="created_at", built_in=True
    )
    contract_date = _field("contract_date", "document", "date")
    approved = _field("approved", "chunk", "boolean")

    predicates, params = build_sql_predicates(
        MetadataFilter(
            document={
                "file_size": {"gte": 10, "lte": 20},
                "upload_date": {"gte": "2026-01-01", "lte": "2026-12-31"},
                "contract_date": {"ne": "2025-12-31"},
            },
            chunk={"approved": False},
        ),
        [file_size, upload_date, contract_date],
        [approved],
    )

    joined = " AND ".join(predicates)
    assert "file_size" not in joined
    assert "contract_date" not in joined
    assert "approved" not in joined
    assert params["doc_key_2"] == "contract_date"
    assert params["chunk_value_0"] is False
    assert params["doc_value_0_gte"] == 10
    assert params["doc_value_0_lte"] == 20
    assert params["doc_value_1_gte"] == "2026-01-01"
    assert params["doc_value_1_lte"] == "2026-12-31"
    assert params["doc_value_2_ne"] == "2025-12-31"


@pytest.mark.parametrize(
    ("filters", "document_fields", "chunk_fields"),
    [
        (
            MetadataFilter(document={"unknown": "x"}),
            [_field("source", "document", "string")],
            [],
        ),
        (
            MetadataFilter(document={"source": "x"}),
            [_field("source", "document", "string", retrieval_filterable=False)],
            [],
        ),
        (
            MetadataFilter(chunk={"status": "bad"}),
            [],
            [_field("status", "chunk", "select", options=["good"])],
        ),
        (
            MetadataFilter(document={"contract_date": "not-a-date"}),
            [_field("contract_date", "document", "date")],
            [],
        ),
        (
            MetadataFilter(chunk={"approved": "yes"}),
            [],
            [_field("approved", "chunk", "boolean")],
        ),
        (
            MetadataFilter(document={"file_size": {"bad": 1}}),
            [_field("file_size", "document", "number")],
            [],
        ),
        (
            MetadataFilter(document={"source' OR true": "x"}),
            [],
            [],
        ),
    ],
)
def test_invalid_filters_reject_param_error(filters, document_fields, chunk_fields):
    with pytest.raises(BizException) as exc:
        build_sql_predicates(filters, document_fields, chunk_fields)

    assert exc.value.code == int(ErrorCode.PARAM_ERROR)


def test_search_sql_joins_documents_and_explicitly_excludes_disabled_assets():
    vector_sql = vector_search._SQL
    fulltext_sql = fulltext_search._SQL

    for sql in (vector_sql, fulltext_sql):
        assert "JOIN documents d ON d.id = c.document_id" in sql
        assert "d.enabled" in sql
        assert "c.enabled" in sql
    assert "ORDER BY c.embedding <=> cast(:emb as vector), c.id" in (
        vector_sql + vector_search._ORDER
    )
    assert "ORDER BY keyword_score DESC, c.id" in (
        fulltext_sql + fulltext_search._ORDER
    )


async def _seed_filter_kb():
    await ensure_admin()
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "MetaFilterKB"))
        await s.commit()
        user = (await s.execute(s.select(User))).scalars().first()
        kb = KnowledgeBase(user_id=user.id, name="MetaFilterKB", scene="general")
        s.add(kb)
        await s.flush()

        s.add_all(
            [
                KbMetadataField(
                    kb_id=kb.id,
                    key="source",
                    name="来源",
                    scope="document",
                    data_type="string",
                    retrieval_filterable=True,
                    built_in=True,
                ),
                KbMetadataField(
                    kb_id=kb.id,
                    key="effective_status",
                    name="效力状态",
                    scope="chunk",
                    data_type="select",
                    options=["现行有效", "已废止"],
                    retrieval_filterable=True,
                ),
            ]
        )

        doc_a = Document(
            kb_id=kb.id,
            user_id=user.id,
            name="招标文件.pdf",
            ext="pdf",
            size=100,
            file_key="filter/a.pdf",
            metadata_={"source": "招标文件"},
            enabled=True,
        )
        doc_b = Document(
            kb_id=kb.id,
            user_id=user.id,
            name="投标文件.pdf",
            ext="pdf",
            size=100,
            file_key="filter/b.pdf",
            metadata_={"source": "投标文件"},
            enabled=False,
        )
        s.add_all([doc_a, doc_b])
        await s.flush()

        chunks = [
            Chunk(
                document_id=doc_a.id,
                kb_id=str(kb.id),
                content="三年质保 A1",
                content_search="三年质保 A1",
                seq=1,
                char_count=8,
                embedding_model="plan_embed_1024",
                embedding=[0.1] * 1024,
                metadata_={"effective_status": "现行有效"},
                enabled=True,
            ),
            Chunk(
                document_id=doc_a.id,
                kb_id=str(kb.id),
                content="三年质保 A2",
                content_search="三年质保 A2",
                seq=2,
                char_count=8,
                embedding_model="plan_embed_1024",
                embedding=[0.1] * 1024,
                metadata_={"effective_status": "已废止"},
                enabled=True,
            ),
            Chunk(
                document_id=doc_b.id,
                kb_id=str(kb.id),
                content="三年质保 B1",
                content_search="三年质保 B1",
                seq=3,
                char_count=8,
                embedding_model="plan_embed_1024",
                embedding=[0.1] * 1024,
                metadata_={"effective_status": "现行有效"},
                enabled=True,
            ),
            Chunk(
                document_id=doc_a.id,
                kb_id=str(kb.id),
                content="三年质保 B2",
                content_search="三年质保 B2",
                seq=4,
                char_count=8,
                embedding_model="plan_embed_1024",
                embedding=[0.1] * 1024,
                metadata_={"effective_status": "现行有效"},
                enabled=False,
            ),
        ]
        s.add_all(chunks)
        await s.commit()
        return str(kb.id)


@pytest.mark.asyncio
async def test_filters_exclude_disabled_assets_and_metadata():
    kb_id = await _seed_filter_kb()

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
    assert all(h["vector_score"] == 1.0 for h in hits)
    assert all(h["keyword_score"] is None for h in hits)


@pytest.mark.asyncio
async def test_fulltext_uses_same_predicates():
    kb_id = await _seed_filter_kb()

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

    assert hits
    assert all(h["document_name"] == "招标文件.pdf" for h in hits)
    assert all(h["metadata"]["effective_status"] == "现行有效" for h in hits)
    assert all(h["keyword_score"] >= 0 for h in hits)
    assert all(h["vector_score"] is None for h in hits)

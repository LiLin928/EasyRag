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
            metadata_={"source": "招标文件"},
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
        s.add_all([kb, test_set])
        await s.flush()
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
        s.add_all([case, run])
        await s.flush()
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

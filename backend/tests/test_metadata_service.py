"""Metadata schema validation and CRUD service tests."""
import inspect
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
from app.services import metadata_service
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
    kb_id, user_id = await _kb("PlanMetaDefaultKB")
    await ensure_default_fields(kb_id, user_id=user_id)
    await ensure_default_fields(kb_id, user_id=user_id)
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
            user_id=user_id,
            scope="chunk",
            payload={"effective_date": "not-a-date"},
        )
    clean = await validate_metadata(
        kb_id=kb_id,
        user_id=user_id,
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


@pytest.mark.asyncio
async def test_validate_metadata_type_rules_without_database(monkeypatch):
    kb_id = uuid.uuid4()
    user_id = uuid.uuid4()
    fields = [
        KbMetadataField(
            kb_id=kb_id,
            key="age",
            name="年龄",
            scope="document",
            data_type="number",
        ),
        KbMetadataField(
            kb_id=kb_id,
            key="active",
            name="生效",
            scope="document",
            data_type="boolean",
        ),
        KbMetadataField(
            kb_id=kb_id,
            key="level",
            name="级别",
            scope="document",
            data_type="select",
            options=["A", "B"],
        ),
    ]
    async def owned_kb(*args, **kwargs):
        return None

    monkeypatch.setattr(metadata_service, "_require_kb", owned_kb)
    clean = await validate_metadata(
        kb_id=kb_id,
        user_id=user_id,
        scope="document",
        payload={"age": 3, "active": True, "level": "A", "unknown": "ignored"},
        fields=fields,
    )
    assert clean == {"age": 3, "active": True, "level": "A"}
    with pytest.raises(BizException):
        await validate_metadata(
            kb_id=kb_id,
            user_id=user_id,
            scope="document",
            payload={"age": True},
            fields=fields,
        )
    with pytest.raises(BizException):
        await validate_metadata(
            kb_id=kb_id,
            user_id=user_id,
            scope="document",
            payload={"active": 1},
            fields=fields,
        )
    with pytest.raises(BizException):
        await validate_metadata(
            kb_id=kb_id,
            user_id=user_id,
            scope="document",
            payload={"level": "C"},
            fields=fields,
        )


@pytest.mark.asyncio
async def test_metadata_authorization_requires_identity_without_database():
    with pytest.raises(BizException) as missing_owner:
        await ensure_default_fields(uuid.uuid4())
    assert missing_owner.value.code == 40001
    signature = inspect.signature(validate_metadata)
    assert signature.parameters["user_id"].default is inspect.Signature.empty

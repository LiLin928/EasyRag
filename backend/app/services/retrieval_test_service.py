"""Ownership-aware CRUD for saved retrieval test sets and cases."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.retrieval_testing import (
    RetrievalTestCase,
    RetrievalTestRun,
    RetrievalTestSet,
)


_SET_FIELDS = {"name", "description", "archived"}
_CASE_FIELDS = {
    "query",
    "expected_doc_ids",
    "expected_chunk_ids",
    "tags",
    "enabled",
    "sort_order",
}


def _uuid(value, label: str) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise BizException(ErrorCode.PARAM_ERROR, f"Invalid {label}") from exc


def _validate_name(name) -> str:
    if not isinstance(name, str) or not name.strip():
        raise BizException(ErrorCode.PARAM_ERROR, "name cannot be blank")
    if len(name) > 100:
        raise BizException(ErrorCode.PARAM_ERROR, "name cannot exceed 100 characters")
    return name


def _validate_query(query) -> str:
    if not isinstance(query, str) or not query.strip():
        raise BizException(ErrorCode.PARAM_ERROR, "query cannot be blank")
    return query


def _validate_tags(tags) -> list[str]:
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise BizException(ErrorCode.PARAM_ERROR, "tags must be a string list")
    if len(tags) > 20:
        raise BizException(ErrorCode.PARAM_ERROR, "tags cannot exceed 20 entries")
    if len(set(tags)) != len(tags):
        raise BizException(ErrorCode.PARAM_ERROR, "tags cannot contain duplicates")
    return list(tags)


def _validate_id_list(values, label: str) -> list[uuid.UUID]:
    if not isinstance(values, list):
        raise BizException(ErrorCode.PARAM_ERROR, f"{label} must be a list")
    return [_uuid(value, label) for value in values]


async def _validate_expected_docs(
    session: AsyncSession, kb_id: uuid.UUID, expected_doc_ids
) -> list[str]:
    ids = _validate_id_list(expected_doc_ids, "expected document ID")
    if not ids:
        return []
    found = set(
        (
            await session.execute(
                select(Document.id).where(
                    Document.id.in_(ids), Document.kb_id == kb_id
                )
            )
        )
        .scalars()
        .all()
    )
    if len(found) != len(set(ids)):
        raise BizException(
            ErrorCode.PARAM_ERROR,
            "expected documents must belong to the test set knowledge base",
        )
    return [str(value) for value in expected_doc_ids]


def _unknown_fields(fields: set, allowed: set, label: str) -> None:
    unknown = fields - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise BizException(ErrorCode.PARAM_ERROR, f"Unknown {label}: {names}")


async def _set_from(
    session: AsyncSession, set_id, user_id, *, for_update: bool = False
) -> RetrievalTestSet:
    set_uuid = _uuid(set_id, "test set ID")
    user_uuid = _uuid(user_id, "user ID")
    query = (
        select(RetrievalTestSet, KnowledgeBase.user_id)
        .join(KnowledgeBase, RetrievalTestSet.kb_id == KnowledgeBase.id)
        .where(RetrievalTestSet.id == set_uuid)
    )
    if for_update:
        query = query.with_for_update(of=RetrievalTestSet)
    row = (await session.execute(query)).first()
    if row is None:
        raise BizException(ErrorCode.NOT_FOUND, "Retrieval test set not found")
    test_set, owner_id = row
    if owner_id != user_uuid:
        raise BizException(ErrorCode.FORBIDDEN, "Retrieval test set not accessible")
    return test_set


async def _case_from(
    session: AsyncSession, case_id, user_id, *, for_update: bool = False
) -> tuple[RetrievalTestCase, RetrievalTestSet]:
    case_uuid = _uuid(case_id, "test case ID")
    user_uuid = _uuid(user_id, "user ID")
    query = (
        select(RetrievalTestCase, RetrievalTestSet, KnowledgeBase.user_id)
        .join(RetrievalTestSet, RetrievalTestCase.test_set_id == RetrievalTestSet.id)
        .join(KnowledgeBase, RetrievalTestSet.kb_id == KnowledgeBase.id)
        .where(RetrievalTestCase.id == case_uuid)
    )
    if for_update:
        query = query.with_for_update(of=RetrievalTestCase)
    row = (await session.execute(query)).first()
    if row is None:
        raise BizException(ErrorCode.NOT_FOUND, "Retrieval test case not found")
    case, test_set, owner_id = row
    if owner_id != user_uuid:
        raise BizException(ErrorCode.FORBIDDEN, "Retrieval test case not accessible")
    return case, test_set


async def list_test_sets(kb_id, user_id, include_archived=False):
    kb_uuid = _uuid(kb_id, "knowledge base ID")
    user_uuid = _uuid(user_id, "user ID")
    filters = [
        KnowledgeBase.id == kb_uuid,
        KnowledgeBase.user_id == user_uuid,
    ]
    if not include_archived:
        filters.append(RetrievalTestSet.archived.is_(False))
    async with async_session() as session:
        kb = (
            await session.execute(
                select(KnowledgeBase).where(KnowledgeBase.id == kb_uuid)
            )
        ).scalar_one_or_none()
        if kb is None:
            raise BizException(ErrorCode.NOT_FOUND, "Knowledge base not found")
        if kb.user_id != user_uuid:
            raise BizException(ErrorCode.FORBIDDEN, "Knowledge base not accessible")
        count = (
            await session.execute(
                select(func.count())
                .select_from(RetrievalTestSet)
                .join(KnowledgeBase, RetrievalTestSet.kb_id == KnowledgeBase.id)
                .where(*filters)
            )
        ).scalar_one()
        rows = (
            await session.execute(
                select(RetrievalTestSet)
                .join(KnowledgeBase, RetrievalTestSet.kb_id == KnowledgeBase.id)
                .where(*filters)
                .order_by(RetrievalTestSet.created_at.desc(), RetrievalTestSet.id)
            )
        ).scalars().all()
        return list(rows), int(count)


async def get_test_set(set_id, user_id):
    async with async_session() as session:
        return await _set_from(session, set_id, user_id)


async def create_test_set(kb_id, user_id, name, description=None):
    kb_uuid = _uuid(kb_id, "knowledge base ID")
    user_uuid = _uuid(user_id, "user ID")
    clean_name = _validate_name(name)
    async with async_session() as session:
        kb = (
            await session.execute(
                select(KnowledgeBase).where(
                    KnowledgeBase.id == kb_uuid, KnowledgeBase.user_id == user_uuid
                )
            )
        ).scalar_one_or_none()
        if kb is None:
            raise BizException(ErrorCode.FORBIDDEN, "Knowledge base not accessible")
        test_set = RetrievalTestSet(
            kb_id=kb.id,
            name=clean_name,
            description=description,
        )
        session.add(test_set)
        await session.commit()
        await session.refresh(test_set)
        return test_set


async def update_test_set(set_id, user_id, **changes):
    _unknown_fields(set(changes), _SET_FIELDS, "test set field")
    async with async_session() as session:
        test_set = await _set_from(session, set_id, user_id, for_update=True)
        if "name" in changes:
            test_set.name = _validate_name(changes["name"])
        if "description" in changes:
            test_set.description = changes["description"]
        if "archived" in changes:
            if not isinstance(changes["archived"], bool):
                raise BizException(ErrorCode.PARAM_ERROR, "archived must be a boolean")
            test_set.archived = changes["archived"]
        await session.commit()
        await session.refresh(test_set)
        return test_set


async def delete_test_set(set_id, user_id):
    async with async_session() as session:
        test_set = await _set_from(session, set_id, user_id, for_update=True)
        await session.delete(test_set)
        await session.commit()


async def list_cases(test_set_id, user_id, enabled: bool | None = None):
    set_uuid = _uuid(test_set_id, "test set ID")
    user_uuid = _uuid(user_id, "user ID")
    filters = [
        RetrievalTestSet.id == set_uuid,
        KnowledgeBase.user_id == user_uuid,
    ]
    if enabled is not None:
        filters.append(RetrievalTestCase.enabled.is_(enabled))
    async with async_session() as session:
        await _set_from(session, set_uuid, user_uuid)
        count = (
            await session.execute(
                select(func.count())
                .select_from(RetrievalTestCase)
                .join(RetrievalTestSet, RetrievalTestCase.test_set_id == RetrievalTestSet.id)
                .join(KnowledgeBase, RetrievalTestSet.kb_id == KnowledgeBase.id)
                .where(*filters)
            )
        ).scalar_one()
        rows = (
            await session.execute(
                select(RetrievalTestCase)
                .join(RetrievalTestSet, RetrievalTestCase.test_set_id == RetrievalTestSet.id)
                .join(KnowledgeBase, RetrievalTestSet.kb_id == KnowledgeBase.id)
                .where(*filters)
                .order_by(
                    RetrievalTestCase.sort_order,
                    RetrievalTestCase.created_at,
                    RetrievalTestCase.id,
                )
            )
        ).scalars().all()
        return list(rows), int(count)


async def create_case(test_set_id, user_id, **fields):
    _unknown_fields(set(fields), _CASE_FIELDS, "test case field")
    if "query" not in fields:
        raise BizException(ErrorCode.PARAM_ERROR, "query is required")
    query = _validate_query(fields["query"])
    tags = _validate_tags(fields.get("tags", []))
    expected_chunk_ids = fields.get("expected_chunk_ids", [])
    if not isinstance(expected_chunk_ids, list):
        raise BizException(ErrorCode.PARAM_ERROR, "expected_chunk_ids must be a list")
    enabled = fields.get("enabled", True)
    if not isinstance(enabled, bool):
        raise BizException(ErrorCode.PARAM_ERROR, "enabled must be a boolean")
    sort_order = fields.get("sort_order", 0)
    if not isinstance(sort_order, int) or isinstance(sort_order, bool):
        raise BizException(ErrorCode.PARAM_ERROR, "sort_order must be an integer")

    async with async_session() as session:
        test_set = await _set_from(session, test_set_id, user_id, for_update=True)
        expected_doc_ids = await _validate_expected_docs(
            session, test_set.kb_id, fields.get("expected_doc_ids", [])
        )
        case = RetrievalTestCase(
            test_set_id=test_set.id,
            query=query,
            expected_doc_ids=expected_doc_ids,
            expected_chunk_ids=list(expected_chunk_ids),
            tags=tags,
            enabled=enabled,
            sort_order=sort_order,
        )
        session.add(case)
        await session.commit()
        await session.refresh(case)
        return case


async def update_case(case_id, user_id, **changes):
    _unknown_fields(set(changes), _CASE_FIELDS, "test case field")
    async with async_session() as session:
        case, test_set = await _case_from(session, case_id, user_id, for_update=True)
        if "query" in changes:
            case.query = _validate_query(changes["query"])
        if "expected_doc_ids" in changes:
            case.expected_doc_ids = await _validate_expected_docs(
                session, test_set.kb_id, changes["expected_doc_ids"]
            )
        if "expected_chunk_ids" in changes:
            if not isinstance(changes["expected_chunk_ids"], list):
                raise BizException(ErrorCode.PARAM_ERROR, "expected_chunk_ids must be a list")
            case.expected_chunk_ids = list(changes["expected_chunk_ids"])
        if "tags" in changes:
            case.tags = _validate_tags(changes["tags"])
        if "enabled" in changes:
            if not isinstance(changes["enabled"], bool):
                raise BizException(ErrorCode.PARAM_ERROR, "enabled must be a boolean")
            case.enabled = changes["enabled"]
        if "sort_order" in changes:
            if not isinstance(changes["sort_order"], int) or isinstance(changes["sort_order"], bool):
                raise BizException(ErrorCode.PARAM_ERROR, "sort_order must be an integer")
            case.sort_order = changes["sort_order"]
        await session.commit()
        await session.refresh(case)
        return case


async def delete_case(case_id, user_id):
    async with async_session() as session:
        case, _ = await _case_from(session, case_id, user_id, for_update=True)
        await session.delete(case)
        await session.commit()


async def batch_case_status(ids, user_id, enabled):
    if not isinstance(enabled, bool):
        raise BizException(ErrorCode.PARAM_ERROR, "enabled must be a boolean")
    id_values = _validate_id_list(ids, "test case ID")
    user_uuid = _uuid(user_id, "user ID")
    async with async_session() as session:
        rows = (
            await session.execute(
                select(RetrievalTestCase)
                .join(RetrievalTestSet, RetrievalTestCase.test_set_id == RetrievalTestSet.id)
                .join(KnowledgeBase, RetrievalTestSet.kb_id == KnowledgeBase.id)
                .where(RetrievalTestCase.id.in_(id_values), KnowledgeBase.user_id == user_uuid)
                .with_for_update(of=RetrievalTestCase)
            )
        ).scalars().all()
        for case in rows:
            case.enabled = enabled
        await session.commit()
        return len(rows)


async def list_runs(test_set_id, user_id):
    set_uuid = _uuid(test_set_id, "test set ID")
    user_uuid = _uuid(user_id, "user ID")
    filters = [
        RetrievalTestSet.id == set_uuid,
        KnowledgeBase.user_id == user_uuid,
    ]
    async with async_session() as session:
        await _set_from(session, set_uuid, user_uuid)
        count = (
            await session.execute(
                select(func.count())
                .select_from(RetrievalTestRun)
                .join(RetrievalTestSet, RetrievalTestRun.test_set_id == RetrievalTestSet.id)
                .join(KnowledgeBase, RetrievalTestSet.kb_id == KnowledgeBase.id)
                .where(*filters)
            )
        ).scalar_one()
        rows = (
            await session.execute(
                select(RetrievalTestRun)
                .join(RetrievalTestSet, RetrievalTestRun.test_set_id == RetrievalTestSet.id)
                .join(KnowledgeBase, RetrievalTestSet.kb_id == KnowledgeBase.id)
                .where(*filters)
                .order_by(RetrievalTestRun.created_at.desc(), RetrievalTestRun.id)
            )
        ).scalars().all()
        return list(rows), int(count)


def _time(value) -> str | None:
    return value.isoformat() if value else None


def test_set_output(test_set: RetrievalTestSet) -> dict:
    return {
        "id": str(test_set.id),
        "kb_id": str(test_set.kb_id),
        "name": test_set.name,
        "description": test_set.description,
        "archived": bool(test_set.archived),
        "created_at": _time(test_set.created_at),
        "updated_at": _time(test_set.updated_at),
    }


def test_case_output(case: RetrievalTestCase) -> dict:
    return {
        "id": str(case.id),
        "test_set_id": str(case.test_set_id),
        "query": case.query,
        "expected_doc_ids": list(case.expected_doc_ids or []),
        "expected_chunk_ids": list(case.expected_chunk_ids or []),
        "tags": list(case.tags or []),
        "enabled": bool(case.enabled),
        "sort_order": case.sort_order,
        "created_at": _time(case.created_at),
        "updated_at": _time(case.updated_at),
    }


def test_run_output(run: RetrievalTestRun) -> dict:
    return {
        "id": str(run.id),
        "test_set_id": str(run.test_set_id),
        "kb_id": str(run.kb_id),
        "status": run.status,
        "config_snapshot": dict(run.config_snapshot or {}),
        "override_config": dict(run.override_config or {}),
        "total_cases": run.total_cases,
        "completed_cases": run.completed_cases,
        "metrics": dict(run.metrics or {}),
        "error": run.error,
        "started_at": _time(run.started_at),
        "finished_at": _time(run.finished_at),
        "created_at": _time(run.created_at),
    }

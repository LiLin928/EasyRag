"""Ownership-aware CRUD for saved retrieval test sets and cases."""
from datetime import datetime, timezone
from time import perf_counter
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.retrieval.metadata_filter import MetadataFilter, build_sql_predicates
from app.core.retrieval.pipeline import RetrievalPipeline
from app.core.retrieval.test_metrics import aggregate_metrics, evaluate_case
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.model_config import ModelConfig
from app.models.retrieval_testing import (
    RetrievalTestCase,
    RetrievalTestCaseResult,
    RetrievalTestRun,
    RetrievalTestSet,
)
from app.providers.langchain_factory import build_embeddings
from app.services import metadata_service
from app.services.retrieval_settings_service import (
    get_effective_settings,
    validate_retrieval_config,
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
_ACTIVE_RUN_STATUSES = ("pending", "running")
_UNFINISHED_RESULT_STATUSES = ("pending", "running")


def _uuid(value, label: str) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise BizException(ErrorCode.PARAM_ERROR, f"Invalid {label}") from exc


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


async def _run_from(
    session: AsyncSession, run_id, user_id, *, for_update: bool = False
) -> tuple[RetrievalTestRun, RetrievalTestSet]:
    run_uuid = _uuid(run_id, "retrieval test run ID")
    user_uuid = _uuid(user_id, "user ID")
    query = (
        select(RetrievalTestRun, RetrievalTestSet, KnowledgeBase.user_id)
        .join(RetrievalTestSet, RetrievalTestRun.test_set_id == RetrievalTestSet.id)
        .join(KnowledgeBase, RetrievalTestRun.kb_id == KnowledgeBase.id)
        .where(RetrievalTestRun.id == run_uuid)
    )
    if for_update:
        query = query.with_for_update(of=RetrievalTestRun)
    row = (await session.execute(query)).first()
    if row is None:
        raise BizException(ErrorCode.NOT_FOUND, "Retrieval test run not found")
    run, test_set, owner_id = row
    if owner_id != user_uuid:
        raise BizException(ErrorCode.FORBIDDEN, "Retrieval test run not accessible")
    return run, test_set


def _validate_ks(ks) -> list[int]:
    if not isinstance(ks, list) or not ks:
        raise BizException(ErrorCode.PARAM_ERROR, "ks cannot be empty")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in ks):
        raise BizException(ErrorCode.PARAM_ERROR, "ks must be an integer list")
    if len(set(ks)) != len(ks):
        raise BizException(ErrorCode.PARAM_ERROR, "ks cannot contain duplicates")
    if any(value < 1 or value > 100 for value in ks):
        raise BizException(ErrorCode.PARAM_ERROR, "ks must be between 1 and 100")
    return sorted(ks)


def _metadata_filter(document_metadata, chunk_metadata) -> MetadataFilter:
    return MetadataFilter(
        document=document_metadata or {},
        chunk=chunk_metadata or {},
    )


async def _validate_metadata_filters(
    kb_id, user_id, document_metadata, chunk_metadata
) -> MetadataFilter:
    if document_metadata is not None and not isinstance(document_metadata, dict):
        raise BizException(ErrorCode.PARAM_ERROR, "document_metadata must be an object")
    if chunk_metadata is not None and not isinstance(chunk_metadata, dict):
        raise BizException(ErrorCode.PARAM_ERROR, "chunk_metadata must be an object")
    filters = _metadata_filter(document_metadata, chunk_metadata)
    if document_metadata:
        fields = await metadata_service.list_fields(kb_id, user_id, "document")
        build_sql_predicates(filters, fields, [])
    if chunk_metadata:
        fields = await metadata_service.list_fields(kb_id, user_id, "chunk")
        build_sql_predicates(filters, [], fields)
    return filters


def _safe_embedding_snapshot(model_info, configured: ModelConfig | None) -> dict | None:
    source = configured.__dict__ if configured is not None else model_info
    if not source:
        return None
    params = (configured.params or {}) if configured is not None else {}
    return {
        "id": str(source["id"]),
        "name": source["name"],
        "prov": source["prov"],
        "dim": params.get("dim"),
    }


def _safe_rerank_snapshot(model_info, configured: ModelConfig | None) -> dict | None:
    source = configured.__dict__ if configured is not None else model_info
    if not source:
        return None
    return {
        "id": str(source["id"]),
        "name": source["name"],
        "prov": source["prov"],
    }


def _selected_models(rows: list[ModelConfig]) -> dict[str, ModelConfig]:
    return {str(model.id): model for model in rows}


def _terminal_message(exc: Exception, model_label: str) -> str:
    if isinstance(exc, BizException):
        return str(exc.message)
    return f"{model_label} model is unavailable"


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


async def start_run(
    *,
    test_set_id,
    user_id,
    case_ids=None,
    ks=None,
    override_config=None,
    document_metadata=None,
    chunk_metadata=None,
) -> RetrievalTestRun:
    clean_ks = _validate_ks([3, 5, 10] if ks is None else ks)
    clean_override = validate_retrieval_config(override_config or {}, partial=True)
    async with async_session() as session:
        test_set = await _set_from(session, test_set_id, user_id, for_update=True)
        active = (
            await session.execute(
                select(RetrievalTestRun)
                .where(
                    RetrievalTestRun.test_set_id == test_set.id,
                    RetrievalTestRun.status.in_(_ACTIVE_RUN_STATUSES),
                )
                .order_by(RetrievalTestRun.created_at.desc(), RetrievalTestRun.id)
            )
        ).scalars().first()
        if active is not None:
            active._newly_created = False
            return active

        case_filters = [
            RetrievalTestCase.test_set_id == test_set.id,
            RetrievalTestCase.enabled.is_(True),
        ]
        selected_ids = None
        if case_ids is not None:
            selected_ids = _validate_id_list(case_ids, "test case ID")
            if len(set(selected_ids)) != len(selected_ids):
                raise BizException(
                    ErrorCode.PARAM_ERROR, "test case IDs cannot contain duplicates"
                )
            if selected_ids:
                case_filters.append(RetrievalTestCase.id.in_(selected_ids))
        cases = (
            await session.execute(
                select(RetrievalTestCase)
                .where(*case_filters)
                .order_by(
                    RetrievalTestCase.sort_order,
                    RetrievalTestCase.created_at,
                    RetrievalTestCase.id,
                )
            )
        ).scalars().all()
        if selected_ids is not None and len(cases) != len(set(selected_ids)):
            raise BizException(
                ErrorCode.PARAM_ERROR,
                "selected cases must belong to the enabled test set",
            )
        if not cases:
            raise BizException(
                ErrorCode.PARAM_ERROR, "No enabled retrieval test cases to run"
            )

        await _validate_metadata_filters(
            test_set.kb_id, user_id, document_metadata, chunk_metadata
        )
        effective = await get_effective_settings(
            test_set.kb_id, user_id=user_id, override=clean_override or None
        )
        embedding_info = effective.get("embedding_model")
        rerank_info = effective.get("rerank_model")
        model_ids = []
        if embedding_info:
            model_ids.append(_uuid(embedding_info["id"], "embedding model ID"))
        if rerank_info:
            model_ids.append(_uuid(rerank_info["id"], "rerank model ID"))
        model_rows = (
            (
                await session.execute(
                    select(ModelConfig).where(ModelConfig.id.in_(model_ids))
                )
            )
            .scalars()
            .all()
            if model_ids
            else []
        )
        models = _selected_models(model_rows)
        config_snapshot = {
            "settings": {
                "values": effective.get("values", {}),
                "resolved": effective.get("resolved", {}),
            },
            "ks": clean_ks,
            "embedding_model": _safe_embedding_snapshot(
                embedding_info,
                models.get(str(embedding_info.get("id"))) if embedding_info else None,
            ),
            "rerank_model": _safe_rerank_snapshot(
                rerank_info,
                models.get(str(rerank_info.get("id"))) if rerank_info else None,
            ),
            "document_metadata": document_metadata or {},
            "chunk_metadata": chunk_metadata or {},
        }
        run = RetrievalTestRun(
            test_set_id=test_set.id,
            kb_id=test_set.kb_id,
            status="pending",
            config_snapshot=config_snapshot,
            override_config=clean_override,
            total_cases=len(cases),
        )
        results = [
            RetrievalTestCaseResult(
                run_id=run.id,
                case_id=case.id,
                query=case.query,
                status="pending",
                expected_doc_ids=list(case.expected_doc_ids or []),
            )
            for case in cases
        ]
        session.add(run)
        session.add_all(results)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            active = (
                await session.execute(
                    select(RetrievalTestRun)
                    .where(
                        RetrievalTestRun.test_set_id == test_set.id,
                        RetrievalTestRun.status.in_(_ACTIVE_RUN_STATUSES),
                    )
                    .order_by(RetrievalTestRun.created_at.desc(), RetrievalTestRun.id)
                )
            ).scalars().first()
            if active is None:
                raise
            active._newly_created = False
            return active
        await session.refresh(run)
        run._newly_created = True
        return run


async def get_run(run_id, user_id) -> RetrievalTestRun:
    async with async_session() as session:
        run, _test_set = await _run_from(session, run_id, user_id)
        return run


async def list_run_cases(run_id, user_id):
    run_uuid = _uuid(run_id, "retrieval test run ID")
    user_uuid = _uuid(user_id, "user ID")
    async with async_session() as session:
        await _run_from(session, run_uuid, user_uuid)
        count = (
            await session.execute(
                select(func.count())
                .select_from(RetrievalTestCaseResult)
                .where(RetrievalTestCaseResult.run_id == run_uuid)
            )
        ).scalar_one()
        rows = (
            await session.execute(
                select(RetrievalTestCaseResult)
                .where(RetrievalTestCaseResult.run_id == run_uuid)
                .order_by(
                    RetrievalTestCaseResult.created_at, RetrievalTestCaseResult.id
                )
            )
        ).scalars().all()
        return list(rows), int(count)


async def cancel_run(run_id, user_id) -> RetrievalTestRun:
    async with async_session() as session:
        run, _test_set = await _run_from(session, run_id, user_id, for_update=True)
        if run.status in _ACTIVE_RUN_STATUSES:
            unfinished = await _load_results(
                session, run.id, _UNFINISHED_RESULT_STATUSES
            )
            for result in unfinished:
                result.status = "skipped"
            run.status = "canceled"
            run.completed_cases = run.total_cases
            run.finished_at = _utcnow()
            await session.commit()
            await session.refresh(run)
        return run


def _normalize_candidates(chunks: list[dict]) -> list[dict]:
    normalized = []
    for rank, chunk in enumerate(chunks, start=1):
        normalized.append(
            {
                "rank": rank,
                "chunk_id": str(chunk.get("id")) if chunk.get("id") is not None else None,
                "document_id": (
                    str(chunk.get("document_id"))
                    if chunk.get("document_id") is not None
                    else None
                ),
                "document_name": chunk.get("document_name"),
                "section_path": chunk.get("section_path"),
                "page_number": chunk.get("page_number"),
                "char_count": chunk.get("char_count"),
                "vector_score": chunk.get("vector_score"),
                "keyword_score": chunk.get("keyword_score"),
                "vector_rank": chunk.get("vector_rank"),
                "keyword_rank": chunk.get("fulltext_rank"),
                "rrf_score": chunk.get("rrf"),
                "rerank_score": chunk.get("rerank_score"),
                "metadata": chunk.get("metadata") or {},
            }
        )
    return normalized


def _apply_case_metrics(
    result: RetrievalTestCaseResult,
    candidates: list[dict],
    ks: list[int],
    retrieval,
) -> None:
    document_ids = [item["document_id"] for item in candidates]
    per_k = {
        str(k): evaluate_case(result.expected_doc_ids or [], document_ids, k=k)
        for k in ks
    }
    final = per_k[str(max(ks))]
    result.hit_doc_ids = list(final["hit_doc_ids"])
    result.results = candidates
    result.metrics = {
        "ks": per_k,
        "rerank_triggered": bool(retrieval.rerank_triggered),
        "rerank_skipped_reason": retrieval.rerank_skipped_reason,
        "navigation_scoped": bool(
            retrieval.nav_info is not None and retrieval.nav_info.get("scoped")
        ),
    }
    result.status = "skipped" if not (result.expected_doc_ids or []) else final["status"]


def _aggregate_case(result: RetrievalTestCaseResult) -> dict:
    per_k = (result.metrics or {}).get("ks", {})
    final = per_k.get(str(max(int(key) for key in per_k)), {}) if per_k else {}
    return {
        "expected_doc_ids": list(result.expected_doc_ids or []),
        "hit_doc_ids": list(result.hit_doc_ids or []),
        "status": result.status,
        "recall": final.get("recall"),
        "reciprocal_rank": final.get("reciprocal_rank"),
        "latency_ms": result.latency_ms,
        "rerank_triggered": (result.metrics or {}).get("rerank_triggered", False),
        "navigation_scoped": (result.metrics or {}).get("navigation_scoped", False),
        "results": list(result.results or []),
    }


async def _load_run(session: AsyncSession, run_id, *, for_update: bool = False):
    run_uuid = _uuid(run_id, "retrieval test run ID")
    query = select(RetrievalTestRun).where(RetrievalTestRun.id == run_uuid)
    if for_update:
        query = query.with_for_update(of=RetrievalTestRun, skip_locked=True)
    return (await session.execute(query)).scalars().first()


async def _load_results(
    session: AsyncSession, run_id: uuid.UUID, statuses=None
) -> list[RetrievalTestCaseResult]:
    rows = (
        await session.execute(
            select(RetrievalTestCaseResult).where(
                RetrievalTestCaseResult.run_id == run_id
            )
        )
    ).scalars().all()
    return [row for row in rows if statuses is None or row.status in statuses]


async def _current_run_status(run_id) -> str | None:
    async with async_session() as session:
        run = await _load_run(session, run_id)
        return run.status if run else None


async def _skip_pending_results(run_id) -> None:
    run_uuid = _uuid(run_id, "retrieval test run ID")
    async with async_session() as session:
        run = await _load_run(session, run_uuid, for_update=True)
        if run is None:
            return
        for result in await _load_results(
            session, run_uuid, _UNFINISHED_RESULT_STATUSES
        ):
            result.status = "skipped"
        await session.commit()


async def _resolve_models(config_snapshot: dict):
    model_ids = []
    embedding_info = config_snapshot.get("embedding_model")
    rerank_info = config_snapshot.get("rerank_model")
    if embedding_info:
        model_ids.append(_uuid(embedding_info["id"], "embedding model ID"))
    if rerank_info:
        model_ids.append(_uuid(rerank_info["id"], "rerank model ID"))
    async with async_session() as session:
        rows = (
            await session.execute(
                select(ModelConfig).where(ModelConfig.id.in_(model_ids))
            )
        ).scalars().all()
    models = _selected_models(rows)
    try:
        if not embedding_info:
            try:
                await build_embeddings()
            except Exception as exc:
                raise RuntimeError(
                    "Embedding model is unavailable"
                ) from exc
        else:
            embedding = models.get(str(embedding_info["id"]))
            if embedding is None or not embedding.enabled or embedding.grp != "embed":
                raise BizException(
                    ErrorCode.PARAM_ERROR, "Embedding model is unavailable"
                )
            dim = (embedding.params or {}).get("dim")
            if dim is not None and dim != 1024:
                raise BizException(
                    ErrorCode.PARAM_ERROR, "Embedding model dimension must be 1024"
                )
        if rerank_info:
            rerank = models.get(str(rerank_info["id"]))
            if rerank is None or not rerank.enabled or rerank.grp != "rerank":
                raise BizException(
                    ErrorCode.PARAM_ERROR, "Rerank model is unavailable"
                )
    except BizException as exc:
        raise RuntimeError(_terminal_message(exc, "Embedding")) from exc
    return embedding_info, rerank_info


async def _mark_run_failed(run_id, error: str) -> None:
    run_uuid = _uuid(run_id, "retrieval test run ID")
    async with async_session() as session:
        run = await _load_run(session, run_uuid, for_update=True)
        if run is None or run.status not in _ACTIVE_RUN_STATUSES:
            return
        for result in await _load_results(
            session, run_uuid, _UNFINISHED_RESULT_STATUSES
        ):
            result.status = "skipped"
        run.status = "failed"
        run.error = error
        run.completed_cases = run.total_cases
        run.finished_at = _utcnow()
        await session.commit()


async def execute_run(run_id: str) -> None:
    run_uuid = _uuid(run_id, "retrieval test run ID")
    async with async_session() as session:
        run = await _load_run(session, run_uuid, for_update=True)
        if run is None or run.status != "pending":
            return
        run.status = "running"
        run.started_at = _utcnow()
        await session.commit()

    try:
        embedding_model, rerank_model = await _resolve_models(run.config_snapshot)
        pipeline = RetrievalPipeline(
            settings=run.config_snapshot["settings"],
            embedding_model=embedding_model,
            rerank_model=rerank_model,
        )
    except Exception as exc:
        await _mark_run_failed(run_uuid, str(exc))
        return

    ks = run.config_snapshot.get("ks") or [3, 5, 10]
    metadata_filter = _metadata_filter(
        run.config_snapshot.get("document_metadata"),
        run.config_snapshot.get("chunk_metadata"),
    )
    while True:
        if await _current_run_status(run_uuid) != "running":
            await _skip_pending_results(run_uuid)
            return
        async with async_session() as session:
            current_run = await _load_run(session, run_uuid)
            pending = await _load_results(
                session, run_uuid, ("pending",)
            )
            if not pending:
                break
            result = pending[0]
            result.status = "running"
            await session.commit()

        started = perf_counter()
        try:
            retrieval = await pipeline.search(
                result.query,
                kb_ids=[str(run.kb_id)],
                doc_ids=None,
                scope=None,
                metadata_filter=metadata_filter,
                top_k=max(ks),
                enable_nav=False,
                count_recall=False,
            )
            latency_ms = max(0, round((perf_counter() - started) * 1000))
            candidates = _normalize_candidates(retrieval.chunks)
            _apply_case_metrics(result, candidates, ks, retrieval)
            result.latency_ms = latency_ms
            error = None
        except Exception as exc:
            latency_ms = max(0, round((perf_counter() - started) * 1000))
            result.status = "failed"
            result.results = []
            result.metrics = {}
            result.hit_doc_ids = []
            result.latency_ms = latency_ms
            result.error = str(exc)
            error = str(exc)

        async with async_session() as session:
            locked_run = await _load_run(session, run_uuid, for_update=True)
            stored = await _load_results(session, run_uuid)
            stored_result = next(
                (item for item in stored if item.id == result.id), None
            )
            if locked_run is None or locked_run.status != "running":
                if stored_result is not None:
                    stored_result.status = "skipped"
                for unfinished in await _load_results(
                    session, run_uuid, _UNFINISHED_RESULT_STATUSES
                ):
                    unfinished.status = "skipped"
                await session.commit()
                return
            if stored_result is not None and stored_result.status == "running":
                stored_result.status = result.status
                stored_result.hit_doc_ids = result.hit_doc_ids
                stored_result.results = result.results
                stored_result.metrics = result.metrics
                stored_result.latency_ms = result.latency_ms
                stored_result.error = error
                locked_run.completed_cases += 1
            await session.commit()

    async with async_session() as session:
        final_run = await _load_run(session, run_uuid, for_update=True)
        if final_run is None or final_run.status != "running":
            for unfinished in await _load_results(
                session, run_uuid, _UNFINISHED_RESULT_STATUSES
            ):
                unfinished.status = "skipped"
            await session.commit()
            return
        results = await _load_results(session, run_uuid)
        final_run.metrics = aggregate_metrics(
            [_aggregate_case(result) for result in results], ks=ks
        )
        final_run.status = "completed"
        final_run.completed_cases = final_run.total_cases
        final_run.finished_at = _utcnow()
        await session.commit()


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


def test_case_result_output(result: RetrievalTestCaseResult) -> dict:
    return {
        "id": str(result.id),
        "run_id": str(result.run_id),
        "case_id": str(result.case_id) if result.case_id else None,
        "query": result.query,
        "status": result.status,
        "expected_doc_ids": list(result.expected_doc_ids or []),
        "hit_doc_ids": list(result.hit_doc_ids or []),
        "results": list(result.results or []),
        "metrics": dict(result.metrics or {}),
        "latency_ms": result.latency_ms,
        "error": result.error,
        "created_at": _time(result.created_at),
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

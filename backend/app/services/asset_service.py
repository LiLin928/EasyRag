"""Ownership-aware document and chunk asset services."""
import uuid
from datetime import datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.metadata import KbMetadataField
from app.services import metadata_service
from app.services.metadata_service import validate_metadata


_SCOPES = {"document", "chunk"}
_SORTS = {
    "created_desc",
    "created_asc",
    "name_asc",
    "name_desc",
    "chunk_count_desc",
    "recall_count_desc",
    "seq_asc",
}
_DOCUMENT_MAPPED_COLUMNS = {
    "document_name": Document.name,
    "file_size": Document.size,
    "uploader": Document.user_id,
    "upload_date": Document.created_at,
    "last_update_date": Document.updated_at,
}


def _uuid(value, label: str) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError):
        raise BizException(ErrorCode.PARAM_ERROR, f"无效的{label}")


def _validate_scope(scope: str) -> None:
    if scope not in _SCOPES:
        raise BizException(ErrorCode.PARAM_ERROR, "资产作用域必须是 document 或 chunk")


def _validate_enabled(enabled: bool) -> None:
    if not isinstance(enabled, bool):
        raise BizException(ErrorCode.PARAM_ERROR, "enabled 必须为布尔值")


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise BizException(ErrorCode.PARAM_ERROR, "page 必须为正整数")
    if (
        not isinstance(page_size, int)
        or isinstance(page_size, bool)
        or page_size < 1
        or page_size > 100
    ):
        raise BizException(ErrorCode.PARAM_ERROR, "page_size 必须在 1 到 100 之间")
    return (page - 1) * page_size, page_size


async def _require_kb(session: AsyncSession, kb_id, user_id) -> KnowledgeBase:
    kb_uuid = _uuid(kb_id, "知识库 ID")
    user_uuid = _uuid(user_id, "用户 ID")
    kb = (
        await session.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_uuid))
    ).scalar_one_or_none()
    if kb is None:
        raise BizException(ErrorCode.NOT_FOUND, "知识库不存在")
    if kb.user_id != user_uuid:
        raise BizException(ErrorCode.FORBIDDEN, "无权访问该知识库")
    return kb


async def _fields(
    session: AsyncSession, kb_id, user_id, scope: str
) -> list[KbMetadataField]:
    kb_uuid = _uuid(kb_id, "知识库 ID")
    user_uuid = _uuid(user_id, "用户 ID")
    return (
        (
            await session.execute(
                select(KbMetadataField)
                .join(KnowledgeBase, KbMetadataField.kb_id == KnowledgeBase.id)
                .where(
                    KnowledgeBase.id == kb_uuid,
                    KnowledgeBase.user_id == user_uuid,
                    KbMetadataField.scope == scope,
                )
                .order_by(KbMetadataField.sort_order, KbMetadataField.created_at)
            )
        )
        .scalars()
        .all()
    )


async def _clean_metadata(
    session: AsyncSession,
    kb_id,
    user_id,
    scope: str,
    payload,
    *,
    require_complete: bool,
) -> dict:
    if not isinstance(payload, dict):
        raise BizException(ErrorCode.PARAM_ERROR, "元数据必须是对象")
    fields = await _fields(session, kb_id, user_id, scope)
    schema = {field.key: field for field in fields}
    unknown = set(payload) - set(schema)
    if unknown:
        raise BizException(
            ErrorCode.PARAM_ERROR,
            f"未知元数据字段: {', '.join(sorted(unknown))}",
        )
    editable = {
        key: value
        for key, value in payload.items()
        if schema[key].mapped_field is None
    }
    return await validate_metadata(
        kb_id=kb_id,
        user_id=user_id,
        scope=scope,
        payload=editable,
        fields=fields,
        require_complete=require_complete,
        partial=not require_complete,
    )


def _date_value(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise BizException(ErrorCode.PARAM_ERROR, "日期筛选值格式不正确") from exc
    return parsed


def _filter_conditions(
    model,
    fields: list[KbMetadataField],
    metadata_filter: dict,
) -> list:
    schema = {field.key: field for field in fields}
    conditions = []
    for key, raw_value in metadata_filter.items():
        field = schema.get(key)
        if field is None:
            raise BizException(ErrorCode.PARAM_ERROR, f"未知元数据字段: {key}")
        if not field.filterable:
            raise BizException(ErrorCode.PARAM_ERROR, f"元数据字段 {key} 不可筛选")
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        if not values:
            raise BizException(ErrorCode.PARAM_ERROR, "元数据筛选值不能为空")
        value_conditions = []
        for value in values:
            metadata_service._validate_value(value, field)
            if model is Document and field.mapped_field is not None:
                column = _DOCUMENT_MAPPED_COLUMNS[field.key]
                if field.key == "uploader":
                    value = _uuid(value, "用户 ID")
                elif field.data_type == "date":
                    value = _date_value(value)
                value_conditions.append(column == value)
            else:
                value_conditions.append(model.metadata_[key] == value)
        conditions.append(or_(*value_conditions))
    return conditions


async def list_documents(
    *,
    kb_id,
    user_id,
    keyword=None,
    status=None,
    enabled=None,
    metadata_filter=None,
    sort="created_desc",
    page=1,
    page_size=20,
) -> tuple[list[Document], int]:
    offset, limit = _pagination(page, page_size)
    if sort not in _SORTS:
        raise BizException(ErrorCode.PARAM_ERROR, "不支持的排序方式")
    if metadata_filter is not None and not isinstance(metadata_filter, dict):
        raise BizException(ErrorCode.PARAM_ERROR, "元数据筛选必须是对象")

    kb_uuid = _uuid(kb_id, "知识库 ID")
    user_uuid = _uuid(user_id, "用户 ID")
    async with async_session() as session:
        await _require_kb(session, kb_uuid, user_uuid)
        filters = [Document.kb_id == kb_uuid, KnowledgeBase.user_id == user_uuid]
        if keyword:
            filters.append(Document.name.ilike(f"%{keyword}%"))
        if status is not None:
            filters.append(Document.status == status)
        if enabled is not None:
            filters.append(Document.enabled == enabled)
        if metadata_filter:
            fields = await _fields(session, kb_uuid, user_uuid, "document")
            filters.extend(
                _filter_conditions(Document, fields, metadata_filter)
            )

        count = (
            await session.execute(
                select(func.count())
                .select_from(Document)
                .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
                .where(*filters)
            )
        ).scalar_one()
        order = {
            "created_desc": Document.created_at.desc(),
            "created_asc": Document.created_at.asc(),
            "name_asc": Document.name.asc(),
            "name_desc": Document.name.desc(),
            "chunk_count_desc": Document.chunk_count.desc(),
            "recall_count_desc": Document.recall_count.desc(),
            "seq_asc": Document.created_at.asc(),
        }[sort]
        rows = (
            await session.execute(
                select(Document)
                .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
                .where(*filters)
                .order_by(order, Document.id.asc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(count)


async def list_chunks(
    *,
    kb_id,
    user_id,
    keyword=None,
    document_id=None,
    vector_state=None,
    enabled=None,
    metadata_filter=None,
    page=1,
    page_size=20,
) -> tuple[list[Chunk], int]:
    offset, limit = _pagination(page, page_size)
    if vector_state not in {None, "all", "vectorized", "pending"}:
        raise BizException(ErrorCode.PARAM_ERROR, "不支持的向量化状态")
    if metadata_filter is not None and not isinstance(metadata_filter, dict):
        raise BizException(ErrorCode.PARAM_ERROR, "元数据筛选必须是对象")

    kb_uuid = _uuid(kb_id, "知识库 ID")
    user_uuid = _uuid(user_id, "用户 ID")
    async with async_session() as session:
        await _require_kb(session, kb_uuid, user_uuid)
        filters = [
            KnowledgeBase.id == kb_uuid,
            KnowledgeBase.user_id == user_uuid,
            Document.kb_id == kb_uuid,
            Chunk.kb_id == str(kb_uuid),
        ]
        if document_id is not None:
            filters.append(Chunk.document_id == _uuid(document_id, "文档 ID"))
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    Chunk.content.ilike(pattern),
                    Chunk.clause_title.ilike(pattern),
                    Chunk.section_path.ilike(pattern),
                )
            )
        if vector_state == "vectorized":
            filters.append(Chunk.embedding.is_not(None))
        elif vector_state == "pending":
            filters.append(Chunk.embedding.is_(None))
        if enabled is not None:
            filters.append(Chunk.enabled == enabled)
        if metadata_filter:
            fields = await _fields(session, kb_uuid, user_uuid, "chunk")
            filters.extend(_filter_conditions(Chunk, fields, metadata_filter))

        count = (
            await session.execute(
                select(func.count())
                .select_from(Chunk)
                .join(Document, Chunk.document_id == Document.id)
                .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
                .where(*filters)
            )
        ).scalar_one()
        rows = (
            await session.execute(
                select(Chunk, Document.name)
                .join(Document, Chunk.document_id == Document.id)
                .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
                .where(*filters)
                .order_by(Chunk.seq.asc(), Chunk.id.asc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        chunks = []
        for chunk, document_name in rows:
            chunk._document_name = document_name
            chunks.append(chunk)
        return chunks, int(count)


async def update_document_metadata(doc_id, user_id, metadata) -> Document:
    user_uuid = _uuid(user_id, "用户 ID")
    async with async_session() as session:
        document = await _document_from(session, doc_id, user_uuid, for_update=True)
        clean = await _clean_metadata(
            session,
            document.kb_id,
            user_uuid,
            "document",
            metadata,
            require_complete=True,
        )
        document.metadata_ = clean
        await session.commit()
        await session.refresh(document)
        return document


async def update_chunk_metadata(chunk_id, user_id, metadata) -> Chunk:
    user_uuid = _uuid(user_id, "用户 ID")
    async with async_session() as session:
        chunk = await _chunk_from(session, chunk_id, user_uuid, for_update=True)
        clean = await _clean_metadata(
            session,
            chunk.kb_id,
            user_uuid,
            "chunk",
            metadata,
            require_complete=True,
        )
        chunk.metadata_ = clean
        await session.commit()
        await session.refresh(chunk)
        return chunk


async def _owned_assets(session, model, ids, user_id, scope: str):
    id_values = [_uuid(value, "资产 ID") for value in ids]
    if scope == "document":
        query = (
            select(Document, KnowledgeBase)
            .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
            .where(Document.id.in_(id_values), KnowledgeBase.user_id == user_id)
            .with_for_update(of=Document)
        )
    else:
        query = (
            select(Chunk, KnowledgeBase)
            .join(Document, Chunk.document_id == Document.id)
            .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
            .where(Chunk.id.in_(id_values), KnowledgeBase.user_id == user_id)
            .with_for_update(of=Chunk)
        )
    return (await session.execute(query)).all()


async def batch_update_metadata(ids, user_id, scope, metadata) -> int:
    _validate_scope(scope)
    user_uuid = _uuid(user_id, "用户 ID")
    async with async_session() as session:
        rows = await _owned_assets(session, scope, ids, user_uuid, scope)
        if not rows:
            return 0
        by_kb = {}
        for asset, kb in rows:
            by_kb.setdefault(kb.id, []).append(asset)
        clean_by_kb = {}
        for kb_id, assets in by_kb.items():
            clean_by_kb[kb_id] = await _clean_metadata(
                session,
                kb_id,
                user_uuid,
                scope,
                metadata,
                require_complete=False,
            )
        for kb_id, assets in by_kb.items():
            for asset in assets:
                current = dict(asset.metadata_ or {})
                current.update(clean_by_kb[kb_id])
                asset.metadata_ = current
        await session.commit()
        return len(rows)


async def batch_update_status(ids, user_id, scope, enabled) -> int:
    _validate_scope(scope)
    _validate_enabled(enabled)
    user_uuid = _uuid(user_id, "用户 ID")
    async with async_session() as session:
        rows = await _owned_assets(session, scope, ids, user_uuid, scope)
        if not rows:
            return 0
        for asset, _ in rows:
            asset.enabled = enabled
        await session.commit()
        return len(rows)


def _date_string(value) -> str:
    return value.date().isoformat() if value else ""


def asset_output(asset, scope: str) -> dict:
    _validate_scope(scope)
    if scope == "document":
        stored = dict(asset.metadata_ or {})
        metadata = {
            "document_name": asset.name,
            "file_size": asset.size,
            "uploader": str(asset.user_id),
            "upload_date": _date_string(asset.created_at),
            "last_update_date": _date_string(asset.updated_at),
        }
        metadata.update(stored)
        return {
            "id": str(asset.id),
            "kb_id": str(asset.kb_id),
            "name": asset.name,
            "ext": asset.ext,
            "size": asset.size,
            "pages": asset.pages,
            "mode": asset.mode,
            "status": asset.status,
            "pct": asset.pct,
            "element_count": asset.element_count,
            "chunk_count": asset.chunk_count,
            "metadata": metadata,
            "enabled": asset.enabled,
            "recall_count": asset.recall_count,
            "created_at": asset.created_at.isoformat() if asset.created_at else "",
        }
    return {
        "id": str(asset.id),
        "kb_id": asset.kb_id,
        "document_id": str(asset.document_id),
        "document_name": getattr(asset, "_document_name", None),
        "content": asset.content,
        "content_search": asset.content_search,
        "clause_title": asset.clause_title,
        "section_path": asset.section_path,
        "page_number": asset.page_number,
        "seq": asset.seq,
        "char_count": asset.char_count,
        "embedding_model": asset.embedding_model,
        "metadata": dict(asset.metadata_ or {}),
        "enabled": asset.enabled,
        "recall_count": asset.recall_count,
        "created_at": asset.created_at.isoformat() if asset.created_at else "",
    }


async def delete_document(document: Document) -> None:
    async with async_session() as session:
        await session.execute(delete(Document).where(Document.id == document.id))
        await session.commit()


async def _document_from(
    session: AsyncSession, doc_id, user_id, *, for_update=False
) -> Document:
    doc_uuid = _uuid(doc_id, "文档 ID")
    query = (
        select(Document, KnowledgeBase.user_id)
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
        .where(Document.id == doc_uuid)
    )
    if for_update:
        query = query.with_for_update(of=Document)
    row = (await session.execute(query)).first()
    if row is None:
        raise BizException(ErrorCode.NOT_FOUND, "文档不存在")
    document, owner_id = row
    if owner_id != user_id:
        raise BizException(ErrorCode.FORBIDDEN, "无权访问该文档")
    return document


async def _chunk_from(
    session: AsyncSession, chunk_id, user_id, *, for_update=False
) -> Chunk:
    chunk_uuid = _uuid(chunk_id, "分块 ID")
    query = (
        select(Chunk, Document.name, KnowledgeBase.user_id)
        .join(Document, Chunk.document_id == Document.id)
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
        .where(Chunk.id == chunk_uuid)
    )
    if for_update:
        query = query.with_for_update(of=Chunk)
    row = (await session.execute(query)).first()
    if row is None:
        raise BizException(ErrorCode.NOT_FOUND, "分块不存在")
    chunk, document_name, owner_id = row
    if owner_id != user_id:
        raise BizException(ErrorCode.FORBIDDEN, "无权访问该分块")
    chunk._document_name = document_name
    return chunk

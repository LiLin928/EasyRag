"""Knowledge-base metadata schema management."""
import math
import re
import uuid
from datetime import datetime

from sqlalchemy import cast, func, select, update
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.metadata import KbMetadataField


BUILTIN_DOCUMENT_FIELDS = [
    {"key": "document_name", "name": "文档名", "mapped_field": "name"},
    {"key": "file_size", "name": "大小", "mapped_field": "size"},
    {"key": "uploader", "name": "上传人", "mapped_field": "user_id"},
    {"key": "upload_date", "name": "上传时间", "mapped_field": "created_at"},
    {"key": "last_update_date", "name": "更新时间", "mapped_field": "updated_at"},
    {"key": "source", "name": "来源", "mapped_field": None},
]

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SCOPES = {"document", "chunk"}
_DATA_TYPES = {"string", "number", "date", "select", "boolean"}
_BUILTIN_TYPES = {
    "document_name": "string",
    "file_size": "number",
    "uploader": "string",
    "upload_date": "date",
    "last_update_date": "date",
    "source": "string",
}
_EDITABLE_FIELDS = {
    "name",
    "options",
    "default_value",
    "required",
    "filterable",
    "retrieval_filterable",
    "visible",
    "sort_order",
}
_BOOL_FIELDS = {
    "required",
    "filterable",
    "retrieval_filterable",
    "visible",
}


def _uuid(value, label: str) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError):
        raise BizException(ErrorCode.PARAM_ERROR, f"无效的{label}")


def _validate_key(key: str) -> None:
    if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
        raise BizException(ErrorCode.PARAM_ERROR, "字段标识必须以小写字母开头，仅含小写字母、数字或下划线")


def _validate_scope(scope: str) -> None:
    if scope not in _SCOPES:
        raise BizException(ErrorCode.PARAM_ERROR, "字段作用域必须是 document 或 chunk")


def _validate_data_type(data_type: str) -> None:
    if data_type not in _DATA_TYPES:
        raise BizException(ErrorCode.PARAM_ERROR, "不支持的字段类型")


def _validate_options(options, data_type: str) -> None:
    if data_type != "select":
        if options:
            raise BizException(ErrorCode.PARAM_ERROR, "仅单选字段可以配置选项")
        return
    if (
        not isinstance(options, list)
        or not options
        or any(not isinstance(option, str) or not option for option in options)
        or len(options) != len(set(options))
    ):
        raise BizException(ErrorCode.PARAM_ERROR, "单选字段选项必须为非空且不重复的字符串列表")


def _validate_value(value, field: KbMetadataField) -> None:
    if value is None:
        raise BizException(ErrorCode.PARAM_ERROR, f"字段 {field.key} 不能为空")

    if field.data_type == "string":
        valid = isinstance(value, str)
    elif field.data_type == "number":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        if valid and isinstance(value, float) and not math.isfinite(value):
            valid = False
    elif field.data_type == "date":
        valid = isinstance(value, str)
        if valid:
            try:
                parsed = datetime.strptime(value, "%Y-%m-%d")
                valid = parsed.strftime("%Y-%m-%d") == value
            except ValueError:
                valid = False
    elif field.data_type == "select":
        valid = isinstance(value, str) and value in (field.options or [])
    else:
        valid = isinstance(value, bool)

    if not valid:
        raise BizException(ErrorCode.PARAM_ERROR, f"字段 {field.key} 的值类型不正确")


async def _seed_default_fields(session: AsyncSession, kb_id) -> None:
    kb_uuid = _uuid(kb_id, "知识库 ID")
    result = await session.execute(
        select(KbMetadataField.key)
        .join(KnowledgeBase, KbMetadataField.kb_id == KnowledgeBase.id)
        .where(
            KnowledgeBase.id == kb_uuid,
            KbMetadataField.scope == "document",
        )
    )
    existing = set(result.scalars())
    for sort_order, definition in enumerate(BUILTIN_DOCUMENT_FIELDS):
        if definition["key"] in existing:
            continue
        session.add(
            KbMetadataField(
                kb_id=kb_uuid,
                key=definition["key"],
                name=definition["name"],
                scope="document",
                data_type=_BUILTIN_TYPES[definition["key"]],
                options=[],
                default_value=None,
                required=False,
                filterable=False,
                retrieval_filterable=False,
                visible=True,
                built_in=True,
                mapped_field=definition["mapped_field"],
                sort_order=sort_order,
            )
        )


async def _require_kb(session: AsyncSession, kb_id, user_id=None) -> KnowledgeBase:
    kb_uuid = _uuid(kb_id, "知识库 ID")
    kb = (
        await session.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_uuid))
    ).scalar_one_or_none()
    if not kb:
        raise BizException(ErrorCode.NOT_FOUND, "知识库不存在")
    if user_id is not None and kb.user_id != _uuid(user_id, "用户 ID"):
        raise BizException(ErrorCode.FORBIDDEN, "无权访问该知识库")
    return kb


async def ensure_default_fields(
    kb_id,
    user_id=None,
    session: AsyncSession | None = None,
) -> None:
    """Idempotently seed built-in document fields for one knowledge base."""
    if session is None and user_id is None:
        raise BizException(ErrorCode.PARAM_ERROR, "缺少知识库归属用户")
    if session is not None:
        if user_id is not None:
            await _require_kb(session, kb_id, user_id)
        await _seed_default_fields(session, kb_id)
        return
    async with async_session() as session:
        await _require_kb(session, kb_id, user_id)
        await _seed_default_fields(session, kb_id)
        await session.commit()


async def list_fields(kb_id, user_id, scope: str | None = None) -> list[KbMetadataField]:
    """List metadata fields for an owned knowledge base."""
    if scope is not None:
        _validate_scope(scope)
    kb_uuid = _uuid(kb_id, "知识库 ID")
    user_uuid = _uuid(user_id, "用户 ID")
    async with async_session() as session:
        await _require_kb(session, kb_uuid, user_uuid)
        query = (
            select(KbMetadataField)
            .join(KnowledgeBase, KbMetadataField.kb_id == KnowledgeBase.id)
            .where(
                KnowledgeBase.id == kb_uuid,
                KnowledgeBase.user_id == user_uuid,
            )
            .order_by(KbMetadataField.sort_order, KbMetadataField.created_at)
        )
        if scope is not None:
            query = query.where(KbMetadataField.scope == scope)
        return (await session.execute(query)).scalars().all()


async def create_field(
    *,
    kb_id,
    user_id,
    key,
    name,
    scope,
    data_type,
    options=None,
    default_value=None,
    required=False,
    filterable=False,
    retrieval_filterable=False,
    visible=True,
    sort_order=0,
) -> KbMetadataField:
    """Create a custom metadata field for an owned knowledge base."""
    _validate_key(key)
    _validate_scope(scope)
    _validate_data_type(data_type)
    _validate_options(options or [], data_type)
    if not isinstance(name, str) or not name.strip():
        raise BizException(ErrorCode.PARAM_ERROR, "字段名称不能为空")

    flag_values = {
        "required": required,
        "filterable": filterable,
        "retrieval_filterable": retrieval_filterable,
        "visible": visible,
    }
    for field_name, flag_value in flag_values.items():
        if not isinstance(flag_value, bool):
            raise BizException(ErrorCode.PARAM_ERROR, f"{field_name} 必须为布尔值")
    if not isinstance(sort_order, int) or isinstance(sort_order, bool):
        raise BizException(ErrorCode.PARAM_ERROR, "sort_order 必须为整数")

    kb_uuid = _uuid(kb_id, "知识库 ID")
    user_uuid = _uuid(user_id, "用户 ID")
    async with async_session() as session:
        await _require_kb(session, kb_uuid, user_uuid)
        duplicate = (
            await session.execute(
                select(KbMetadataField)
                .join(KnowledgeBase, KbMetadataField.kb_id == KnowledgeBase.id)
                .where(
                    KnowledgeBase.id == kb_uuid,
                    KnowledgeBase.user_id == user_uuid,
                    KbMetadataField.scope == scope,
                    KbMetadataField.key == key,
                )
            )
        ).scalar_one_or_none()
        if duplicate:
            raise BizException(ErrorCode.PARAM_ERROR, f"字段 {key} 已存在")

        field = KbMetadataField(
            kb_id=kb_uuid,
            key=key,
            name=name,
            scope=scope,
            data_type=data_type,
            options=list(options or []),
            default_value=default_value,
            required=required,
            filterable=filterable,
            retrieval_filterable=retrieval_filterable,
            visible=visible,
            built_in=False,
            mapped_field=None,
            sort_order=sort_order,
        )
        if default_value is not None:
            _validate_value(default_value, field)
        session.add(field)
        await session.commit()
        await session.refresh(field)
        return field


async def update_field(field_id, user_id, kb_id=None, **changes) -> KbMetadataField:
    """Update allowed metadata-field attributes for an owned field."""
    field_uuid = _uuid(field_id, "字段 ID")
    user_uuid = _uuid(user_id, "用户 ID")
    unsupported = set(changes) - _EDITABLE_FIELDS
    immutable = set(changes) & {"key", "scope", "data_type"}
    if unsupported or immutable:
        raise BizException(ErrorCode.PARAM_ERROR, "字段包含不可修改的属性")

    async with async_session() as session:
        query = (
            select(KbMetadataField)
            .join(KnowledgeBase, KbMetadataField.kb_id == KnowledgeBase.id)
            .where(
                KbMetadataField.id == field_uuid,
                KnowledgeBase.user_id == user_uuid,
            )
        )
        if kb_id is not None:
            query = query.where(KnowledgeBase.id == _uuid(kb_id, "知识库 ID"))
        field = (await session.execute(query)).scalar_one_or_none()
        if not field:
            raise BizException(ErrorCode.NOT_FOUND, "字段不存在")

        if field.built_in and "required" in changes:
            raise BizException(ErrorCode.FORBIDDEN, "内置字段不能修改必填属性")
        if "name" in changes and (
            not isinstance(changes["name"], str) or not changes["name"].strip()
        ):
            raise BizException(ErrorCode.PARAM_ERROR, "字段名称不能为空")
        if "options" in changes:
            if changes["options"] is None:
                changes["options"] = []
            _validate_options(changes["options"], field.data_type)
            if field.default_value is not None:
                probe = KbMetadataField(
                    data_type=field.data_type,
                    options=changes["options"],
                    key=field.key,
                )
                _validate_value(field.default_value, probe)
        for field_name in _BOOL_FIELDS:
            if field_name in changes and not isinstance(changes[field_name], bool):
                raise BizException(ErrorCode.PARAM_ERROR, f"{field_name} 必须为布尔值")
        if "sort_order" in changes and (
            not isinstance(changes["sort_order"], int)
            or isinstance(changes["sort_order"], bool)
        ):
            raise BizException(ErrorCode.PARAM_ERROR, "sort_order 必须为整数")
        if "default_value" in changes and changes["default_value"] is not None:
            probe = KbMetadataField(
                data_type=field.data_type,
                options=changes.get("options", field.options),
                key=field.key,
            )
            _validate_value(changes["default_value"], probe)

        for field_name, value in changes.items():
            setattr(field, field_name, list(value or []) if field_name == "options" else value)
        await session.commit()
        await session.refresh(field)
        return field


async def delete_field(field_id, user_id, kb_id=None, force=False) -> dict:
    """Delete a custom field and optionally strip its stored JSON values."""
    field_uuid = _uuid(field_id, "字段 ID")
    user_uuid = _uuid(user_id, "用户 ID")
    async with async_session() as session:
        query = (
            select(KbMetadataField)
            .join(KnowledgeBase, KbMetadataField.kb_id == KnowledgeBase.id)
            .where(
                KbMetadataField.id == field_uuid,
                KnowledgeBase.user_id == user_uuid,
            )
        )
        if kb_id is not None:
            query = query.where(KnowledgeBase.id == _uuid(kb_id, "知识库 ID"))
        field = (await session.execute(query)).scalar_one_or_none()
        if not field:
            raise BizException(ErrorCode.NOT_FOUND, "字段不存在")
        if field.built_in:
            raise BizException(ErrorCode.FORBIDDEN, "内置字段不可删除")

        if field.scope == "document":
            count_query = (
                select(func.count())
                .select_from(Document)
                .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
                .where(
                    KnowledgeBase.id == field.kb_id,
                    KnowledgeBase.user_id == user_uuid,
                    Document.metadata_.has_key(field.key),
                )
            )
        else:
            count_query = (
                select(func.count())
                .select_from(Chunk)
                .join(
                    KnowledgeBase,
                    KnowledgeBase.id == cast(Chunk.kb_id, PostgresUUID),
                )
                .where(
                    KnowledgeBase.id == field.kb_id,
                    KnowledgeBase.user_id == user_uuid,
                    Chunk.metadata_.has_key(field.key),
                )
            )
        affected_count = (await session.execute(count_query)).scalar_one()

        if affected_count and not force:
            return {"success": False, "affected_count": affected_count}

        if affected_count and force:
            if field.scope == "document":
                await session.execute(
                    update(Document)
                    .where(
                        Document.kb_id == field.kb_id,
                        Document.metadata_.has_key(field.key),
                    )
                    .values(metadata_=Document.metadata_ - field.key)
                )
            else:
                await session.execute(
                    update(Chunk)
                    .where(
                        Chunk.kb_id == str(field.kb_id),
                        Chunk.metadata_.has_key(field.key),
                    )
                    .values(metadata_=Chunk.metadata_ - field.key)
                )

        await session.delete(field)
        await session.commit()
        return {"success": True, "affected_count": affected_count}


async def validate_metadata(
    *,
    kb_id,
    user_id,
    scope,
    payload,
    fields=None,
    require_complete=False,
    partial=False,
) -> dict:
    """Validate payload keys against a knowledge-base schema and strip unknown keys."""
    _validate_scope(scope)
    if not isinstance(payload, dict):
        raise BizException(ErrorCode.PARAM_ERROR, "元数据必须是对象")
    kb_uuid = _uuid(kb_id, "知识库 ID")
    user_uuid = _uuid(user_id, "用户 ID")

    if fields is None:
        async with async_session() as session:
            await _require_kb(session, kb_uuid, user_uuid)
            fields = (
                await session.execute(
                    select(KbMetadataField)
                    .join(KnowledgeBase, KbMetadataField.kb_id == KnowledgeBase.id)
                    .where(
                        KnowledgeBase.id == kb_uuid,
                        KnowledgeBase.user_id == user_uuid,
                        KbMetadataField.scope == scope,
                    )
                )
            ).scalars().all()
    else:
        async with async_session() as session:
            await _require_kb(session, kb_uuid, user_uuid)
        fields = [
            field
            for field in fields
            if field.kb_id == kb_uuid and field.scope == scope
        ]

    schema = {field.key: field for field in fields}
    clean = {}
    for key, value in payload.items():
        field = schema.get(key)
        if field is None or field.mapped_field is not None:
            continue
        _validate_value(value, field)
        clean[key] = value

    if require_complete or not partial:
        missing = [
            field.key
            for field in fields
            if field.required
            and field.mapped_field is None
            and field.key not in payload
        ]
        if missing:
            raise BizException(ErrorCode.PARAM_ERROR, f"缺少必填元数据字段: {', '.join(missing)}")
    return clean

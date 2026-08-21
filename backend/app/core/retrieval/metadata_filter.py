"""Safe metadata predicate construction for retrieval SQL."""
from dataclasses import dataclass, field
from datetime import date
import math
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BizException, ErrorCode
from app.models.metadata import KbMetadataField


@dataclass(frozen=True)
class MetadataFilter:
    document: dict[str, object] = field(default_factory=dict)
    chunk: dict[str, object] = field(default_factory=dict)


_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte"}

_DOCUMENT_PHYSICAL_FIELDS = {
    "document_name": "d.name",
    "file_size": "d.size",
    "uploader": "d.user_id::text",
    "upload_date": "d.created_at::date::text",
    "last_update_date": "d.updated_at::date::text",
}


def _param_error(message: str) -> BizException:
    return BizException(ErrorCode.PARAM_ERROR, message)


def _parse_date(value: object, key: str) -> str:
    if not isinstance(value, str):
        raise _param_error(f"Invalid date value for {key}")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise _param_error(f"Invalid date value for {key}") from exc
    if parsed.isoformat() != value:
        raise _param_error(f"Invalid date value for {key}")
    return value


def _validate_number(value: object, key: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _param_error(f"Invalid number value for {key}")
    if isinstance(value, float) and not math.isfinite(value):
        raise _param_error(f"Invalid number value for {key}")
    return value


def _validate_scalar(value: object, field: KbMetadataField) -> object:
    key = field.key
    if field.data_type in ("string", "select"):
        if not isinstance(value, str):
            raise _param_error(f"Invalid string value for {key}")
        if field.data_type == "select" and value not in (field.options or []):
            raise _param_error(f"Value is not an option for {key}")
        return value
    if field.data_type == "number":
        return _validate_number(value, key)
    if field.data_type == "date":
        return _parse_date(value, key)
    if field.data_type == "boolean":
        if not isinstance(value, bool):
            raise _param_error(f"Invalid boolean value for {key}")
        return value
    raise _param_error(f"Unsupported metadata type for {key}")


def _field_expression(field: KbMetadataField, alias: str, key_param: str | None) -> str:
    if field.scope == "document" and field.key in _DOCUMENT_PHYSICAL_FIELDS:
        return _DOCUMENT_PHYSICAL_FIELDS[field.key]
    return f"{alias}.metadata ->> {key_param}"


def _cast(expression: str, data_type: str) -> str:
    if data_type == "number":
        return f"cast({expression} as numeric)"
    if data_type == "date":
        return f"cast({expression} as date)"
    if data_type == "boolean":
        return f"cast({expression} as boolean)"
    return expression


def _sql_operator(operator: str) -> str:
    return {"eq": "=", "ne": "!="}.get(operator, operator)


def _build_field_predicates(
    field: KbMetadataField,
    value: object,
    prefix: str,
    index: int,
    alias: str,
) -> tuple[list[str], dict[str, object]]:
    key = field.key
    key_param = f"{prefix}_key_{index}"
    params: dict[str, object] = {key_param: key}
    expression = _field_expression(field, alias, key_param)
    value_prefix = f"{prefix}_value_{index}"

    if isinstance(value, dict):
        unknown = set(value) - _OPERATORS
        if not value or unknown:
            raise _param_error(f"Invalid filter operator for {key}")
        predicates = []
        for operator, raw_value in value.items():
            validated = _validate_scalar(raw_value, field)
            value_param = f"{value_prefix}_{operator}"
            params[value_param] = validated
            sql_operator = _sql_operator(operator)
            predicates.append(
                f"{_cast(expression, field.data_type)} {sql_operator} :{value_param}"
            )
        return predicates, params

    values = value if isinstance(value, list) else [value]
    if not values:
        raise _param_error(f"Filter value for {key} cannot be empty")
    validated_values = [_validate_scalar(item, field) for item in values]
    value_param = value_prefix
    params[value_param] = validated_values if isinstance(value, list) else validated_values[0]

    if isinstance(value, list):
        array_type = {"number": "numeric[]"}.get(field.data_type, "text[]")
        predicate = (
            f"{_cast(expression, field.data_type)} = "
            f"ANY(cast(:{value_param} as {array_type}))"
        )
    else:
        predicate = f"{_cast(expression, field.data_type)} = :{value_param}"
    return [predicate], params


def build_sql_predicates(
    filters: MetadataFilter,
    document_fields: list[KbMetadataField],
    chunk_fields: list[KbMetadataField],
) -> tuple[list[str], dict[str, object]]:
    """Build parameter-bound predicates against a trusted metadata schema."""
    predicates: list[str] = []
    params: dict[str, object] = {}

    schemas = {
        "document": {
            field.key: field
            for field in document_fields
            if field.scope == "document" and field.retrieval_filterable
        },
        "chunk": {
            field.key: field
            for field in chunk_fields
            if field.scope == "chunk" and field.retrieval_filterable
        },
    }

    for scope, raw_filters in (
        ("document", filters.document),
        ("chunk", filters.chunk),
    ):
        if not isinstance(raw_filters, dict):
            raise _param_error(f"{scope} metadata filter must be an object")
        for index, (key, value) in enumerate(raw_filters.items()):
            field = schemas[scope].get(key)
            if field is None:
                raise _param_error(f"Unknown retrieval filter field: {key}")
            scope_prefix = "doc" if scope == "document" else "chunk"
            scope_predicates, scope_params = _build_field_predicates(
                field, value, scope_prefix, index, "d" if scope == "document" else "c"
            )
            predicates.extend(scope_predicates)
            params.update(scope_params)

    return predicates, params


async def build_predicates_for_kbs(
    session: AsyncSession,
    kb_ids: list[str],
    filters: MetadataFilter | None,
) -> tuple[list[str], dict[str, object]]:
    """Validate a filter against every selected KB schema in one session."""
    if filters is None or (not filters.document and not filters.chunk):
        return [], {}
    if not kb_ids:
        raise _param_error("At least one knowledge base is required for metadata filtering")

    try:
        kb_uuids = list(dict.fromkeys(uuid.UUID(kb_id) for kb_id in kb_ids))
    except (TypeError, ValueError) as exc:
        raise _param_error("Invalid knowledge base ID") from exc

    rows = (
        await session.execute(
            select(KbMetadataField).where(KbMetadataField.kb_id.in_(kb_uuids))
        )
    ).scalars().all()
    by_kb: dict[uuid.UUID, list[KbMetadataField]] = {kb_id: [] for kb_id in kb_uuids}
    for row in rows:
        by_kb[row.kb_id].append(row)

    predicates: list[str] = []
    params: dict[str, object] = {}
    for fields in by_kb.values():
        predicates, params = build_sql_predicates(
            filters,
            [field for field in fields if field.scope == "document"],
            [field for field in fields if field.scope == "chunk"],
        )
    return predicates, params

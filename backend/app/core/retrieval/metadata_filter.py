"""Safe metadata predicate construction for retrieval SQL."""
from dataclasses import dataclass, field
from datetime import date
import math
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BizException, ErrorCode
from app.models.metadata import KbMetadataField


# 时间戳格式正则表达式（ISO 8601）
TIMESTAMP_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$')

# 字段名安全验证正则（字母、数字、下划线，不能以数字开头）
FIELD_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


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
    """创建参数错误异常。

    Args:
        message: 错误消息

    Returns:
        BizException 实例
    """
    return BizException(ErrorCode.PARAM_ERROR, message)


def _parse_date(value: object, key: str) -> str:
    """解析并验证日期字符串。

    Args:
        value: 待验证的值
        key: 字段键名（用于错误消息）

    Returns:
        验证通过的日期字符串

    Raises:
        BizException: 日期格式无效
    """
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
    """验证数值类型的有效性。

    Args:
        value: 待验证的值
        key: 字段键名（用于错误消息）

    Returns:
        验证通过的数值

    Raises:
        BizException: 数值无效或不是数值类型
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _param_error(f"Invalid number value for {key}")
    if isinstance(value, float) and not math.isfinite(value):
        raise _param_error(f"Invalid number value for {key}")
    return value


def _validate_scalar(value: object, field: KbMetadataField) -> object:
    """根据字段定义验证标量值。

    Args:
        value: 待验证的值
        field: 字段定义对象

    Returns:
        验证通过的值

    Raises:
        BizException: 值不符合字段定义
    """
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
    """构建字段访问的SQL表达式。

    Args:
        field: 字段定义对象
        alias: 表别名
        key_param: 字段键名参数名

    Returns:
        SQL字段访问表达式
    """
    if field.scope == "document" and field.key in _DOCUMENT_PHYSICAL_FIELDS:
        return _DOCUMENT_PHYSICAL_FIELDS[field.key]
    return f"{alias}.metadata ->> {key_param}"


def _cast(expression: str, data_type: str) -> str:
    """为表达式添加类型转换。

    Args:
        expression: SQL表达式
        data_type: 目标数据类型

    Returns:
        带类型转换的SQL表达式
    """
    if data_type == "number":
        return f"cast({expression} as numeric)"
    if data_type == "date":
        return f"cast({expression} as date)"
    if data_type == "boolean":
        return f"cast({expression} as boolean)"
    return expression


def _sql_operator(operator: str) -> str:
    """转换操作符名称为SQL操作符。

    Args:
        operator: 操作符名称（eq, ne等）

    Returns:
        SQL操作符（=, !=等）
    """
    return {"eq": "=", "ne": "!="}.get(operator, operator)


def _build_field_predicates(
    field: KbMetadataField,
    value: object,
    prefix: str,
    index: int,
    alias: str,
) -> tuple[list[str], dict[str, object]]:
    """构建字段的过滤谓词。

    Args:
        field: 字段定义对象
        value: 过滤值（可以是单个值、列表或操作符映射）
        prefix: 参数名前缀
        index: 字段索引
        alias: 表别名

    Returns:
        (谓词列表, 参数字典) 元组

    Raises:
        BizException: 操作符无效或值验证失败
    """
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
    """根据元数据过滤条件和字段定义构建SQL谓词。

    这是核心函数，用于将元数据过滤条件转换为可执行的SQL谓词列表和参数字典。
    所有字段都基于知识库的元数据配置进行验证，确保类型安全。

    Args:
        filters: 元数据过滤条件对象
        document_fields: 文档级字段定义列表
        chunk_fields: 分块级字段定义列表

    Returns:
        (谓词列表, 参数字典) 元组，可直接用于SQL查询

    Raises:
        BizException: 字段不存在或值验证失败

    Example:
        >>> filters = MetadataFilter(document={"author": "Alice"})
        >>> fields = [KbMetadataField(key="author", scope="document", data_type="string")]
        >>> predicates, params = build_sql_predicates(filters, fields, [])
        >>> predicates
        ['d.metadata ->> :doc_key_0 = :doc_value_0_eq']
    """
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
    """为多个知识库构建统一的元数据过滤谓词。

    此函数会从数据库加载所有知识库的元数据字段定义，并对每个知识库验证过滤条件，
    然后合并所有谓词和参数，确保参数名不会冲突。

    Args:
        session: 数据库会话
        kb_ids: 知识库ID列表
        filters: 元数据过滤条件对象

    Returns:
        (谓词列表, 参数字典) 元组，所有知识库的谓词已合并

    Raises:
        BizException: 知识库ID无效或字段不存在

    Example:
        >>> async with session:
        ...     predicates, params = await build_predicates_for_kbs(
        ...         session, ["kb-uuid-1", "kb-uuid-2"], filters
        ...     )
    """
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

    all_predicates: list[str] = []
    all_params: dict[str, object] = {}
    for kb_index, fields in enumerate(by_kb.values()):
        predicates, params = build_sql_predicates(
            filters,
            [field for field in fields if field.scope == "document"],
            [field for field in fields if field.scope == "chunk"],
        )
        # Namespace param keys to avoid collisions across KBs
        namespaced = {f"kb{kb_index}_{k}": v for k, v in params.items()}
        for p in predicates:
            for old_key in params:
                p = p.replace(f":{old_key}", f":kb{kb_index}_{old_key}")
            all_predicates.append(p)
        all_params.update(namespaced)
    return all_predicates, all_params


class MetadataFilterBuilder:
    """元数据过滤SQL构建器。

    将DSL格式的过滤条件转换为SQL WHERE子句和参数。

    Attributes:
        supported_operators: 支持的操作符列表
    """

    SUPPORTED_OPERATORS = ["=", "!=", ">", ">=", "<", "<=", "IN", "LIKE"]

    @staticmethod
    def _is_timestamp(value: str) -> bool:
        """验证字符串是否为时间戳格式。

        Args:
            value: 待验证的字符串

        Returns:
            是否为有效的时间戳格式

        Examples:
            >>> MetadataFilterBuilder._is_timestamp("2026-01-01")
            True
            >>> MetadataFilterBuilder._is_timestamp("2026-01-01T10:30:00")
            True
            >>> MetadataFilterBuilder._is_timestamp("P-1")
            False
        """
        return bool(TIMESTAMP_PATTERN.match(value))

    @staticmethod
    def _validate_field_name(field: str) -> str:
        """验证字段名安全性，防止SQL注入。

        Args:
            field: 字段名

        Returns:
            验证通过的字段名

        Raises:
            BizException: 字段名格式非法

        Examples:
            >>> MetadataFilterBuilder._validate_field_name("department")
            'department'
            >>> MetadataFilterBuilder._validate_field_name("user_name")
            'user_name'
            >>> MetadataFilterBuilder._validate_field_name("'; DROP TABLE users; --")
            BizException: Invalid field name
        """
        if not FIELD_NAME_PATTERN.match(field):
            raise _param_error(f"Invalid field name: {field}")
        return field

    def build_where_clause(
        self,
        filters: dict[str, object] | None,
        table_alias: str = "chunks"
    ) -> tuple[str, dict[str, object]]:
        """构建WHERE子句和参数。

        Args:
            filters: DSL格式的过滤条件
            table_alias: 表别名

        Returns:
            (where_clause, params) 元组

        Raises:
            BizException: 不支持的操作符或格式错误
        """
        if not filters:
            return "TRUE", {}

        logic = filters.get("logic", "AND").upper()
        conditions = filters.get("conditions", [])

        if not conditions:
            return "TRUE", {}

        sql_conditions = []
        params = {}

        for idx, cond in enumerate(conditions):
            if "logic" in cond:
                # 递归处理嵌套条件
                sub_clause, sub_params = self.build_where_clause(cond, table_alias)
                sql_conditions.append(f"({sub_clause})")
                # 重新编号参数以避免冲突
                for key, value in sub_params.items():
                    params[f"p{len(params)}"] = value
            else:
                # 处理叶子条件
                clause, clause_params = self._build_leaf_condition(
                    cond, len(params), table_alias
                )
                sql_conditions.append(clause)
                params.update(clause_params)

        where_clause = f" {logic} ".join(sql_conditions)
        return where_clause, params

    def _build_leaf_condition(
        self,
        condition: dict[str, object],
        param_start_idx: int,
        table_alias: str
    ) -> tuple[str, dict[str, object]]:
        """构建单个条件的SQL。

        Args:
            condition: 单个条件字典
            param_start_idx: 参数起始索引
            table_alias: 表别名

        Returns:
            (clause, params) 元组

        Raises:
            BizException: 不支持的操作符或格式错误
        """
        field = condition["field"]
        operator = condition["operator"]
        value = condition["value"]

        # 验证操作符
        if operator not in self.SUPPORTED_OPERATORS:
            raise _param_error(f"不支持的操作符: {operator}")

        # 验证字段名安全性
        field = self._validate_field_name(field)

        # JSONB字段访问：metadata->>'field'（字段名已验证安全）
        field_expr = f"{table_alias}.metadata->>'{field}'"

        if operator == "=":
            param_name = f"p{param_start_idx}"
            return f"{field_expr} = :{param_name}", {param_name: str(value)}

        elif operator == "!=":
            param_name = f"p{param_start_idx}"
            return f"{field_expr} != :{param_name}", {param_name: str(value)}

        elif operator == ">":
            param_name = f"p{param_start_idx}"
            return f"({field_expr})::float > :{param_name}::float", {param_name: str(value)}

        elif operator == ">=":
            param_name = f"p{param_start_idx}"
            # 使用严格的时间戳格式验证
            if isinstance(value, str) and self._is_timestamp(value):
                # 时间戳
                return f"({field_expr})::timestamp >= :{param_name}::timestamp", {param_name: str(value)}
            else:
                # 数字
                return f"({field_expr})::float >= :{param_name}::float", {param_name: str(value)}

        elif operator == "<":
            param_name = f"p{param_start_idx}"
            return f"({field_expr})::float < :{param_name}::float", {param_name: str(value)}

        elif operator == "<=":
            param_name = f"p{param_start_idx}"
            # 使用严格的时间戳格式验证
            if isinstance(value, str) and self._is_timestamp(value):
                return f"({field_expr})::timestamp <= :{param_name}::timestamp", {param_name: str(value)}
            else:
                return f"({field_expr})::float <= :{param_name}::float", {param_name: str(value)}

        elif operator == "IN":
            if not isinstance(value, list):
                raise _param_error("IN操作符的值必须是列表")

            placeholders = []
            params = {}
            for i, v in enumerate(value):
                param_name = f"p{param_start_idx + i}"
                placeholders.append(f":{param_name}")
                params[param_name] = str(v)

            return f"{field_expr} IN ({', '.join(placeholders)})", params

        elif operator == "LIKE":
            param_name = f"p{param_start_idx}"
            return f"{field_expr} LIKE :{param_name}", {param_name: str(value)}

        return "TRUE", {}

        return "TRUE", {}

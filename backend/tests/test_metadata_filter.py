"""元数据过滤函数式API测试。

测试 build_sql_predicates 和 build_predicates_for_kbs 的基本功能。
"""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.retrieval.metadata_filter import (
    MetadataFilter,
    build_predicates_for_kbs,
    build_sql_predicates,
)


def _field(key, scope, data_type="string", retrieval_filterable=True, options=None):
    """创建轻量级的字段对象用于测试。

    使用 SimpleNamespace 避免 SQLAlchemy mapped_column 问题。
    只设置 metadata_filter 实际读取的属性。

    Args:
        key: 字段键名
        scope: 字段作用域（document 或 chunk）
        data_type: 数据类型（string, number, date, boolean, select）
        retrieval_filterable: 是否可检索过滤
        options: 选项列表（仅用于 select 类型）

    Returns:
        字段对象
    """
    return SimpleNamespace(
        key=key,
        scope=scope,
        data_type=data_type,
        retrieval_filterable=retrieval_filterable,
        options=options,
    )


class TestBuildSqlPredicates:
    """测试 build_sql_predicates 函数。"""

    def test_single_document_filter(self):
        """测试单个文档级过滤条件。"""
        fields = [_field("author", "document", "string")]
        filters = MetadataFilter(document={"author": "Alice"})

        predicates, params = build_sql_predicates(filters, fields, [])

        assert len(predicates) == 1
        assert "Alice" in str(params.values())

    def test_single_chunk_filter(self):
        """测试单个分块级过滤条件。"""
        fields = [_field("level", "chunk", "number")]
        filters = MetadataFilter(chunk={"level": {"gte": 3}})

        predicates, params = build_sql_predicates(filters, [], fields)

        assert len(predicates) == 1
        assert 3 in params.values()

    def test_multiple_filters(self):
        """测试多个过滤条件。"""
        doc_fields = [_field("author", "document", "string")]
        chunk_fields = [_field("level", "chunk", "number")]

        filters = MetadataFilter(
            document={"author": "Bob"},
            chunk={"level": {"gt": 2}}
        )

        predicates, params = build_sql_predicates(filters, doc_fields, chunk_fields)

        assert len(predicates) == 2
        assert "Bob" in str(params.values())
        assert 2 in params.values()

    def test_empty_filter(self):
        """测试空过滤条件。"""
        filters = MetadataFilter()
        predicates, params = build_sql_predicates(filters, [], [])

        assert predicates == []
        assert params == {}

    def test_list_value_filter(self):
        """测试列表值过滤条件。"""
        fields = [_field("tags", "document", "string")]
        filters = MetadataFilter(document={"tags": ["tag1", "tag2"]})

        predicates, params = build_sql_predicates(filters, fields, [])

        assert len(predicates) == 1
        # 列表值应该转换为数组查询
        assert "ANY" in predicates[0]

    def test_select_field_with_valid_option(self):
        """测试选项字段的有效值。"""
        fields = [_field("status", "document", "select", options=["active", "inactive"])]
        filters = MetadataFilter(document={"status": "active"})

        predicates, params = build_sql_predicates(filters, fields, [])

        assert len(predicates) == 1
        assert "active" in str(params.values())

    def test_date_field_filter(self):
        """测试日期字段过滤。"""
        fields = [_field("create_date", "document", "date")]
        filters = MetadataFilter(document={"create_date": {"gte": "2026-01-01"}})

        predicates, params = build_sql_predicates(filters, fields, [])

        assert len(predicates) == 1
        assert "cast" in predicates[0]
        assert "date" in predicates[0]

    def test_document_physical_field(self):
        """测试文档物理字段（直接映射到表字段）。"""
        fields = [_field("document_name", "document", "string")]
        filters = MetadataFilter(document={"document_name": "test.pdf"})

        predicates, params = build_sql_predicates(filters, fields, [])

        assert len(predicates) == 1
        # 应该使用物理字段映射而不是 JSONB 访问
        assert "d.name" in predicates[0]


class TestBuildPredicatesForKbs:
    """测试 build_predicates_for_kbs 函数。"""

    @pytest.mark.asyncio
    async def test_single_kb_filter(self):
        """测试单个知识库的过滤。"""
        kb_id = uuid.uuid4()
        f1 = _field("author", "document", "string")
        f1.kb_id = kb_id

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [f1]
        session = AsyncMock()
        session.execute.return_value = mock_result

        filters = MetadataFilter(document={"author": "Alice"})
        predicates, params = await build_predicates_for_kbs(
            session, [str(kb_id)], filters
        )

        assert len(predicates) == 1

    @pytest.mark.asyncio
    async def test_multi_kb_filter(self):
        """测试多个知识库的过滤（验证参数命名空间隔离）。"""
        kb1 = uuid.uuid4()
        kb2 = uuid.uuid4()

        f1 = _field("author", "document", "string")
        f1.kb_id = kb1
        f2 = _field("author", "document", "string")
        f2.kb_id = kb2

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [f1, f2]
        session = AsyncMock()
        session.execute.return_value = mock_result

        filters = MetadataFilter(document={"author": "Alice"})
        predicates, params = await build_predicates_for_kbs(
            session, [str(kb1), str(kb2)], filters
        )

        # 两个知识库都应该贡献谓词
        assert len(predicates) == 2
        # 参数键应该是唯一的（通过 kb0_, kb1_ 前缀隔离）
        param_keys = list(params.keys())
        assert len(param_keys) == len(set(param_keys))

    @pytest.mark.asyncio
    async def test_none_filter_returns_empty(self):
        """测试 None 过滤条件返回空结果。"""
        session = AsyncMock()
        predicates, params = await build_predicates_for_kbs(
            session, ["some-id"], None
        )

        assert predicates == []
        assert params == {}

    @pytest.mark.asyncio
    async def test_empty_filter_returns_empty(self):
        """测试空过滤条件返回空结果。"""
        session = AsyncMock()
        predicates, params = await build_predicates_for_kbs(
            session, ["some-id"], MetadataFilter()
        )

        assert predicates == []
        assert params == {}
"""元数据过滤构建器测试。"""
import pytest
from app.core.retrieval.metadata_filter import MetadataFilterBuilder


def test_simple_equality_condition():
    """测试简单等值条件。"""
    builder = MetadataFilterBuilder()
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "department", "operator": "=", "value": "研发部"}
        ]
    }

    where_clause, params = builder.build_where_clause(filters)

    # 验证生成的SQL包含正确的条件
    assert "metadata->>'department' = :p0" in where_clause
    assert params == {"p0": "研发部"}


def test_empty_filters():
    """测试空过滤条件。"""
    builder = MetadataFilterBuilder()

    where_clause, params = builder.build_where_clause(None)

    assert where_clause == "TRUE"
    assert params == {}


def test_invalid_operator():
    """测试非法操作符。"""
    builder = MetadataFilterBuilder()
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "status", "operator": "INVALID", "value": "test"}
        ]
    }

    with pytest.raises(ValueError, match="不支持的操作符"):
        builder.build_where_clause(filters)


def test_in_operator():
    """测试IN操作符。"""
    builder = MetadataFilterBuilder()
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "status", "operator": "IN", "value": ["已审核", "待审核"]}
        ]
    }

    where_clause, params = builder.build_where_clause(filters)

    assert "IN (" in where_clause
    assert "p0" in params
    assert "p1" in params
    assert params["p0"] == "已审核"
    assert params["p1"] == "待审核"


def test_range_condition():
    """测试范围条件。"""
    builder = MetadataFilterBuilder()
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "create_time", "operator": ">=", "value": "2026-01-01"}
        ]
    }

    where_clause, params = builder.build_where_clause(filters)

    assert ">=" in where_clause
    assert "timestamp" in where_clause
    assert params["p0"] == "2026-01-01"


def test_like_operator():
    """测试LIKE操作符。"""
    builder = MetadataFilterBuilder()
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "title", "operator": "LIKE", "value": "%安全%"}
        ]
    }

    where_clause, params = builder.build_where_clause(filters)

    assert "LIKE" in where_clause
    assert params["p0"] == "%安全%"


def test_nested_conditions():
    """测试嵌套条件。"""
    builder = MetadataFilterBuilder()
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "department", "operator": "=", "value": "研发部"},
            {
                "logic": "OR",
                "conditions": [
                    {"field": "level", "operator": ">", "value": 3},
                    {"field": "priority", "operator": "=", "value": "高"}
                ]
            }
        ]
    }

    where_clause, params = builder.build_where_clause(filters)

    assert "AND" in where_clause
    assert "OR" in where_clause
    assert "(" in where_clause  # 嵌套条件有括号


def test_multiple_conditions():
    """测试多个条件组合。"""
    builder = MetadataFilterBuilder()
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "department", "operator": "=", "value": "研发部"},
            {"field": "status", "operator": "!=", "value": "草稿"},
            {"field": "level", "operator": ">=", "value": 2}
        ]
    }

    where_clause, params = builder.build_where_clause(filters)

    assert where_clause.count("AND") == 2
    assert len(params) == 3
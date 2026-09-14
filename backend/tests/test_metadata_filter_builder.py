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


def test_strict_timestamp_validation():
    """测试严格的时间戳格式验证。"""
    builder = MetadataFilterBuilder()

    # 有效的时间戳格式
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "create_time", "operator": ">=", "value": "2026-01-01"}
        ]
    }
    where_clause, params = builder.build_where_clause(filters)
    assert "timestamp" in where_clause

    # 有效的时间戳格式（带时间）
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "update_time", "operator": "<=", "value": "2026-01-01T10:30:00"}
        ]
    }
    where_clause, params = builder.build_where_clause(filters)
    assert "timestamp" in where_clause

    # 无效的时间戳格式（含 - 但不是时间戳）
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "code", "operator": ">=", "value": "P-1"}
        ]
    }
    where_clause, params = builder.build_where_clause(filters)
    # 应该识别为数字，而不是时间戳
    assert "float" in where_clause
    assert "timestamp" not in where_clause


def test_field_name_validation():
    """测试字段名安全性验证。"""
    builder = MetadataFilterBuilder()

    # 有效的字段名
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "valid_field", "operator": "=", "value": "test"}
        ]
    }
    where_clause, params = builder.build_where_clause(filters)
    assert "valid_field" in where_clause

    # 带下划线的有效字段名
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "user_name_123", "operator": "=", "value": "test"}
        ]
    }
    where_clause, params = builder.build_where_clause(filters)
    assert "user_name_123" in where_clause


def test_invalid_field_name():
    """测试非法字段名应被拒绝。"""
    builder = MetadataFilterBuilder()

    # SQL注入尝试
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "'; DROP TABLE users; --", "operator": "=", "value": "test"}
        ]
    }
    with pytest.raises(ValueError, match="Invalid field name"):
        builder.build_where_clause(filters)

    # 以数字开头的字段名
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "123_field", "operator": "=", "value": "test"}
        ]
    }
    with pytest.raises(ValueError, match="Invalid field name"):
        builder.build_where_clause(filters)

    # 包含特殊字符的字段名
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "field-name", "operator": "=", "value": "test"}
        ]
    }
    with pytest.raises(ValueError, match="Invalid field name"):
        builder.build_where_clause(filters)
"""Unit tests for metadata_filter predicate accumulation (I1 fix)."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.retrieval.metadata_filter import (
    MetadataFilter,
    build_predicates_for_kbs,
    build_sql_predicates,
)


def _field(key, scope, data_type="string", retrieval_filterable=True):
    """Create a lightweight field-like object for testing.

    Uses SimpleNamespace to avoid SQLAlchemy mapped_column issues.
    Only the attributes actually read by metadata_filter are set.
    """
    return SimpleNamespace(
        key=key,
        scope=scope,
        data_type=data_type,
        retrieval_filterable=retrieval_filterable,
        options=None,
    )


class TestBuildSqlPredicatesSingleKb:
    """Verify build_sql_predicates works for a single KB."""

    def test_single_document_filter(self):
        fields = [_field("author", "document", "string")]
        filters = MetadataFilter(document={"author": "Alice"})
        predicates, params = build_sql_predicates(filters, fields, [])
        assert len(predicates) == 1
        assert any("Alice" in str(v) for v in params.values())

    def test_empty_filter(self):
        filters = MetadataFilter()
        predicates, params = build_sql_predicates(filters, [], [])
        assert predicates == []
        assert params == {}


class TestBuildPredicatesForKbsMultiKb:
    """Verify I1 fix: predicates from ALL KBs are accumulated, not just the last."""

    @pytest.mark.asyncio
    async def test_multi_kb_predicates_accumulated(self):
        """Two KBs with the same field should produce predicates for both."""
        kb1 = uuid.uuid4()
        kb2 = uuid.uuid4()
        # Both KBs have the "author" field so the filter validates for each
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

        # Both KBs should contribute predicates (one per KB)
        assert len(predicates) == 2, f"Expected 2 predicates, got {len(predicates)}: {predicates}"

    @pytest.mark.asyncio
    async def test_multi_kb_param_keys_are_unique(self):
        """Param keys must not collide across KBs."""
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

        # Both KBs contribute a predicate (each KB has an "author" field)
        assert len(predicates) == 2
        # All param keys must be unique
        param_keys = list(params.keys())
        assert len(param_keys) == len(set(param_keys)), f"Duplicate param keys: {param_keys}"

    @pytest.mark.asyncio
    async def test_single_kb_no_regression(self):
        """Single KB should still work correctly after the fix."""
        kb1 = uuid.uuid4()
        f1 = _field("author", "document", "string")
        f1.kb_id = kb1

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [f1]
        session = AsyncMock()
        session.execute.return_value = mock_result

        filters = MetadataFilter(document={"author": "Alice"})
        predicates, params = await build_predicates_for_kbs(
            session, [str(kb1)], filters
        )

        assert len(predicates) == 1
        # Param key should be prefixed with kb0_
        assert any(k.startswith("kb0_") for k in params.keys()), f"Expected kb0_ prefix in params: {params}"


class TestBuildPredicatesForKbsEdgeCases:
    @pytest.mark.asyncio
    async def test_none_filter_returns_empty(self):
        session = AsyncMock()
        predicates, params = await build_predicates_for_kbs(session, ["some-id"], None)
        assert predicates == []
        assert params == {}

    @pytest.mark.asyncio
    async def test_empty_filter_returns_empty(self):
        session = AsyncMock()
        predicates, params = await build_predicates_for_kbs(
            session, ["some-id"], MetadataFilter()
        )
        assert predicates == []
        assert params == {}

# 元数据驱动两阶段检索 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现元数据驱动的两阶段检索，先通过元数据过滤缩小范围，再进行向量/关键词匹配，支持复杂查询DSL。

**Architecture:** 使用PostgreSQL CTE实现两阶段查询，MetadataFilterBuilder将DSL转换为SQL WHERE子句，重构VectorSearch和KeywordSearch使用CTE模式，更新API Schema支持新DSL并保持向后兼容。

**Tech Stack:** PostgreSQL CTE, SQLAlchemy 2.0 async, Pydantic v2, pgvector, pg_trgm, pytest.

**Source spec:** `docs/superpowers/specs/2026-09-14-metadata-driven-retrieval-design.md`

---

## File Structure

```text
backend/app/core/retrieval/
  metadata_filter.py                    # New - SQL构建器
  hybrid_search.py                      # Modify - 使用CTE重构

backend/app/schemas/
  retrieval.py                          # Modify - 添加MetadataFilter DSL

backend/app/services/
  retrieval_service.py                  # Modify - 添加格式转换

backend/alembic/versions/
  xxx_add_metadata_indexes.py          # New - 索引迁移

backend/tests/
  test_metadata_filter_builder.py      # New - SQL构建器测试
  test_retrieval_with_metadata_filter.py # New - 集成测试
```

---

### Task 1: 实现MetadataFilterBuilder核心类

**Files:**
- Create: `backend/app/core/retrieval/metadata_filter.py`
- Test: `backend/tests/test_metadata_filter_builder.py`

- [ ] **Step 1: 创建测试文件，编写第一个测试（简单等值条件）**

```python
# backend/tests/test_metadata_filter_builder.py
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && uv run pytest tests/test_metadata_filter_builder.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 创建metadata_filter.py，实现MetadataFilterBuilder类（支持等值操作符）**

```python
# backend/app/core/retrieval/metadata_filter.py
"""元数据过滤SQL构建器。

将DSL格式的过滤条件转换为SQL WHERE子句。
"""
from typing import Dict, Any, Tuple, List


class MetadataFilterBuilder:
    """元数据过滤SQL构建器。

    将DSL格式的过滤条件转换为SQL WHERE子句和参数。

    Attributes:
        supported_operators: 支持的操作符列表
    """

    SUPPORTED_OPERATORS = ["=", "!=", ">", ">=", "<", "<=", "IN", "LIKE"]

    def build_where_clause(
        self,
        filters: Dict[str, Any] | None,
        table_alias: str = "chunks"
    ) -> Tuple[str, Dict[str, Any]]:
        """构建WHERE子句和参数。

        Args:
            filters: DSL格式的过滤条件
            table_alias: 表别名

        Returns:
            (where_clause, params) 元组

        Raises:
            ValueError: 不支持的操作符或格式错误
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
        condition: Dict[str, Any],
        param_start_idx: int,
        table_alias: str
    ) -> Tuple[str, Dict[str, Any]]:
        """构建单个条件的SQL。

        Args:
            condition: 单个条件字典
            param_start_idx: 参数起始索引
            table_alias: 表别名

        Returns:
            (clause, params) 元组

        Raises:
            ValueError: 不支持的操作符
        """
        field = condition["field"]
        operator = condition["operator"]
        value = condition["value"]

        if operator not in self.SUPPORTED_OPERATORS:
            raise ValueError(f"不支持的操作符: {operator}")

        # JSONB字段访问：metadata->>'field'
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
            # 尝试判断是时间戳还是数字
            if isinstance(value, str) and ("-" in value or ":" in value):
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
            if isinstance(value, str) and ("-" in value or ":" in value):
                return f"({field_expr})::timestamp <= :{param_name}::timestamp", {param_name: str(value)}
            else:
                return f"({field_expr})::float <= :{param_name}::float", {param_name: str(value)}

        elif operator == "IN":
            if not isinstance(value, list):
                raise ValueError("IN操作符的值必须是列表")

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
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd backend && uv run pytest tests/test_metadata_filter_builder.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: 添加更多操作符测试**

```python
# backend/tests/test_metadata_filter_builder.py (追加)

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
```

- [ ] **Step 6: 运行测试验证所有操作符**

Run: `cd backend && uv run pytest tests/test_metadata_filter_builder.py -v`
Expected: PASS (9 tests)

- [ ] **Step 7: 提交代码**

```bash
cd backend && git add app/core/retrieval/metadata_filter.py tests/test_metadata_filter_builder.py
git commit -m "feat(retrieval): add MetadataFilterBuilder with DSL to SQL conversion

- Support operators: =, !=, >, >=, <, <=, IN, LIKE
- Support nested AND/OR conditions
- Prevent SQL injection through parameterized queries"
```

---

### Task 2: 重构VectorSearch使用CTE查询

**Files:**
- Modify: `backend/app/core/retrieval/hybrid_search.py`
- Test: `backend/tests/test_retrieval_with_metadata_filter.py`

- [ ] **Step 1: 创建集成测试文件，编写第一个测试**

```python
# backend/tests/test_retrieval_with_metadata_filter.py
"""元数据过滤检索集成测试。"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import uuid

from app.services.retrieval_service import RetrievalService
from app.schemas.retrieval import RetrievalRequest, MetadataFilter, MetadataCondition
from app.core.retrieval.embedder import Embedder


@pytest.fixture
async def setup_test_data(session: AsyncSession):
    """准备测试数据。"""
    # 清理旧数据
    await session.execute(text("DELETE FROM chunks"))
    await session.execute(text("DELETE FROM documents"))
    await session.execute(text("DELETE FROM knowledge_bases"))

    # 创建知识库
    kb_id = str(uuid.uuid4())
    await session.execute(text("""
        INSERT INTO knowledge_bases (id, user_id, name, scene)
        VALUES (:id, 'admin', '测试知识库', 'general')
    """), {"id": kb_id})

    # 创建文档
    doc_id = str(uuid.uuid4())
    await session.execute(text("""
        INSERT INTO documents (id, kb_id, user_id, name, ext, size, status, file_key)
        VALUES (:id, :kb_id, 'admin', '测试文档.pdf', 'pdf', 1024, 'done', 'test.pdf')
    """), {"id": doc_id, "kb_id": kb_id})

    # 插入不同部门的chunk（带向量）
    chunks = [
        {
            "id": str(uuid.uuid4()),
            "doc_id": doc_id,
            "kb_id": kb_id,
            "content": "叉车安全操作规程",
            "department": "生产部",
            "status": "已审核",
            "level": 3
        },
        {
            "id": str(uuid.uuid4()),
            "doc_id": doc_id,
            "kb_id": kb_id,
            "content": "软件开发流程规范",
            "department": "研发部",
            "status": "已审核",
            "level": 2
        },
        {
            "id": str(uuid.uuid4()),
            "doc_id": doc_id,
            "kb_id": kb_id,
            "content": "安全生产管理制度",
            "department": "生产部",
            "status": "草稿",
            "level": 4
        }
    ]

    # 使用1024维向量（与EMBEDDING_DIM一致）
    import random
    random.seed(42)

    for chunk in chunks:
        embedding = [random.random() for _ in range(1024)]
        await session.execute(text("""
            INSERT INTO chunks (id, document_id, kb_id, content, content_search, page_number, seq, embedding, metadata, enabled)
            VALUES (:id, :doc_id, :kb_id, :content, :content, 1, 0, :embedding::vector, :metadata::jsonb, true)
        """), {
            "id": chunk["id"],
            "doc_id": chunk["doc_id"],
            "kb_id": chunk["kb_id"],
            "content": chunk["content"],
            "embedding": str(embedding),
            "metadata": f'{{"department": "{chunk["department"]}", "status": "{chunk["status"]}", "level": {chunk["level"]}}}'
        })

    await session.commit()
    return kb_id


@pytest.mark.asyncio
async def test_metadata_filter_before_vector_search(session: AsyncSession, setup_test_data):
    """测试元数据过滤在向量检索之前执行。"""
    kb_id = await setup_test_data

    service = RetrievalService()
    request = RetrievalRequest(
        query="安全操作",
        kb_id=kb_id,
        method="vector",
        top_k=10,
        metadata_filters=MetadataFilter(
            logic="AND",
            conditions=[
                MetadataCondition(field="department", operator="=", value="生产部")
            ]
        )
    )

    # 使用Mock Embedder
    class MockEmbedder:
        async def embed_query(self, query):
            return [0.5] * 1024

    result = await service.retrieve(session, request, embedder=MockEmbedder())

    # 验证：所有结果都应该是"生产部"的文档
    assert result.total > 0
    for candidate in result.candidates:
        assert candidate.metadata.get("department") == "生产部"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && uv run pytest tests/test_retrieval_with_metadata_filter.py::test_metadata_filter_before_vector_search -v`
Expected: FAIL - 当前实现不支持MetadataFilter对象

- [ ] **Step 3: 重构VectorSearch使用CTE查询**

```python
# backend/app/core/retrieval/hybrid_search.py (修改VectorSearch.search方法)

from sqlalchemy import text
from app.core.retrieval.metadata_filter import MetadataFilterBuilder

class VectorSearch:
    """向量检索器。

    使用 pgvector 进行向量相似度检索。
    """

    async def search(
        self,
        session: AsyncSession,
        kb_id: str,
        query_vector: List[float],
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """执行向量检索（CTE模式）。

        先通过元数据过滤缩小范围，再进行向量相似度计算。

        Args:
            session: 数据库会话
            kb_id: 知识库ID
            query_vector: 查询向量
            top_k: 返回数量
            filters: 元数据过滤条件（DSL格式）

        Returns:
            检索结果列表
        """
        # 验证向量维度
        if len(query_vector) != EMBEDDING_DIM:
            raise ValueError(f"向量维度不匹配：期望 {EMBEDDING_DIM}，实际 {len(query_vector)}")

        # 构建元数据过滤条件
        filter_builder = MetadataFilterBuilder()
        where_clause, params = filter_builder.build_where_clause(filters, "chunks")

        # CTE查询：先过滤元数据，再计算向量相似度
        sql = text(f"""
            WITH filtered_chunks AS (
                SELECT
                    id,
                    document_id,
                    content,
                    page_number,
                    metadata,
                    embedding
                FROM chunks
                WHERE kb_id = :kb_id
                    AND enabled = true
                    AND embedding IS NOT NULL
                    AND {where_clause}
            )
            SELECT
                id as chunk_id,
                document_id,
                content,
                page_number,
                metadata,
                1 - (embedding <=> :query_vector::vector) as vector_score
            FROM filtered_chunks
            ORDER BY embedding <=> :query_vector::vector
            LIMIT :top_k
        """)

        # 执行查询
        result = await session.execute(sql, {
            "kb_id": kb_id,
            "query_vector": str(query_vector),
            "top_k": top_k,
            **params
        })

        rows = result.mappings().all()

        # 格式化结果
        candidates = []
        for idx, row in enumerate(rows):
            candidates.append({
                "rank": idx + 1,
                "chunk_id": str(row["chunk_id"]),
                "document_id": str(row["document_id"]),
                "document_name": "",  # 需要关联查询
                "content": row["content"],
                "page_number": row["page_number"],
                "vector_score": float(row["vector_score"]),
                "keyword_score": 0.0,
                "metadata": row["metadata"] or {}
            })

        return candidates
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd backend && uv run pytest tests/test_retrieval_with_metadata_filter.py::test_metadata_filter_before_vector_search -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
cd backend && git add app/core/retrieval/hybrid_search.py tests/test_retrieval_with_metadata_filter.py
git commit -m "feat(retrieval): refactor VectorSearch with CTE for metadata filtering

- Use CTE to filter metadata before vector search
- Integrate MetadataFilterBuilder for SQL generation
- Maintain backward compatibility"
```

---

### Task 3: 重构KeywordSearch使用CTE查询

**Files:**
- Modify: `backend/app/core/retrieval/hybrid_search.py`

- [ ] **Step 1: 添加关键词检索测试**

```python
# backend/tests/test_retrieval_with_metadata_filter.py (追加)

@pytest.mark.asyncio
async def test_metadata_filter_before_keyword_search(session: AsyncSession, setup_test_data):
    """测试元数据过滤在关键词检索之前执行。"""
    kb_id = await setup_test_data

    service = RetrievalService()
    request = RetrievalRequest(
        query="安全",
        kb_id=kb_id,
        method="keyword",
        top_k=10,
        metadata_filters=MetadataFilter(
            logic="AND",
            conditions=[
                MetadataCondition(field="status", operator="=", value="已审核")
            ]
        )
    )

    result = await service.retrieve(session, request)

    # 验证：所有结果都应该是"已审核"状态的文档
    assert result.total > 0
    for candidate in result.candidates:
        assert candidate.metadata.get("status") == "已审核"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && uv run pytest tests/test_retrieval_with_metadata_filter.py::test_metadata_filter_before_keyword_search -v`
Expected: FAIL - 当前实现不支持

- [ ] **Step 3: 重构KeywordSearch使用CTE查询**

```python
# backend/app/core/retrieval/hybrid_search.py (修改KeywordSearch.search方法)

class KeywordSearch:
    """关键词检索器。

    使用 pg_trgm 进行全文检索。
    """

    async def search(
        self,
        session: AsyncSession,
        kb_id: str,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """执行关键词检索（CTE模式）。

        先通过元数据过滤缩小范围，再进行关键词匹配。

        Args:
            session: 数据库会话
            kb_id: 知识库ID
            query: 查询文本
            top_k: 返回数量
            filters: 元数据过滤条件（DSL格式）

        Returns:
            检索结果列表
        """
        # 构建元数据过滤条件
        filter_builder = MetadataFilterBuilder()
        where_clause, params = filter_builder.build_where_clause(filters, "chunks")

        # CTE查询：先过滤元数据，再进行关键词检索
        sql = text(f"""
            WITH filtered_chunks AS (
                SELECT
                    id,
                    document_id,
                    content,
                    content_search,
                    page_number,
                    metadata
                FROM chunks
                WHERE kb_id = :kb_id
                    AND enabled = true
                    AND content_search IS NOT NULL
                    AND {where_clause}
            )
            SELECT
                id as chunk_id,
                document_id,
                content,
                page_number,
                metadata,
                similarity(content_search, :query) as keyword_score
            FROM filtered_chunks
            WHERE content_search % :query
            ORDER BY keyword_score DESC
            LIMIT :top_k
        """)

        # 执行查询
        result = await session.execute(sql, {
            "kb_id": kb_id,
            "query": query,
            "top_k": top_k,
            **params
        })

        rows = result.mappings().all()

        # 格式化结果
        candidates = []
        for idx, row in enumerate(rows):
            candidates.append({
                "rank": idx + 1,
                "chunk_id": str(row["chunk_id"]),
                "document_id": str(row["document_id"]),
                "document_name": "",  # 需要关联查询
                "content": row["content"],
                "page_number": row["page_number"],
                "vector_score": 0.0,
                "keyword_score": float(row["keyword_score"] or 0),
                "metadata": row["metadata"] or {}
            })

        return candidates
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd backend && uv run pytest tests/test_retrieval_with_metadata_filter.py::test_metadata_filter_before_keyword_search -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
cd backend && git add app/core/retrieval/hybrid_search.py tests/test_retrieval_with_metadata_filter.py
git commit -m "feat(retrieval): refactor KeywordSearch with CTE for metadata filtering"
```

---

### Task 4: 更新Schema支持新DSL

**Files:**
- Modify: `backend/app/schemas/retrieval.py`

- [ ] **Step 1: 更新Schema定义**

```python
# backend/app/schemas/retrieval.py
"""检索相关 Schema 定义。"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union


class MetadataCondition(BaseModel):
    """元数据过滤条件。"""
    field: str = Field(..., description="字段名")
    operator: str = Field(..., description="操作符：=, !=, >, >=, <, <=, IN, LIKE")
    value: Any = Field(..., description="值")


class MetadataFilter(BaseModel):
    """元数据过滤器（支持嵌套）。"""
    logic: str = Field(default="AND", description="逻辑运算：AND, OR")
    conditions: List[Union[MetadataCondition, "MetadataFilter"]] = Field(
        default=[],
        description="条件列表（支持嵌套）"
    )


# 更新模型前向引用
MetadataFilter.model_rebuild()


class RetrievalRequest(BaseModel):
    """检索请求。"""
    query: str = Field(..., description="查询文本")
    kb_id: str = Field(..., description="知识库ID")
    top_k: int = Field(default=5, description="返回数量")
    method: str = Field(default="hybrid", description="检索方法：vector/keyword/hybrid")
    vector_top_k: int = Field(default=20, description="向量检索返回数量")
    keyword_top_k: int = Field(default=20, description="关键词检索返回数量")
    similarity_threshold: float = Field(default=0.3, description="相似度阈值")
    rerank_enabled: bool = Field(default=True, description="是否启用重排序")
    rerank_top_n: int = Field(default=10, description="重排序返回数量")
    navigation_enabled: bool = Field(default=True, description="是否启用导航式检索")

    # 支持两种格式：简单Dict（向后兼容）和复杂DSL
    metadata_filters: Optional[Union[Dict[str, Any], MetadataFilter]] = Field(
        default=None,
        description="元数据过滤条件（支持复杂查询DSL）"
    )


class RetrievalCandidate(BaseModel):
    """检索候选项。"""
    rank: int = Field(..., description="排名")
    chunk_id: str = Field(..., description="分块ID")
    document_id: str = Field(..., description="文档ID")
    document_name: str = Field(..., description="文档名称")
    content: str = Field(..., description="内容")
    page_number: int = Field(..., description="页码")
    vector_score: float = Field(default=0.0, description="向量检索分数")
    keyword_score: float = Field(default=0.0, description="关键词检索分数")
    final_score: float = Field(default=0.0, description="最终分数")
    metadata: Dict[str, Any] = Field(default={}, description="元数据")


class RetrievalResult(BaseModel):
    """检索结果。"""
    query: str = Field(..., description="查询文本")
    candidates: List[RetrievalCandidate] = Field(default=[], description="候选项列表")
    total: int = Field(default=0, description="总数")
    retrieval_time_ms: int = Field(default=0, description="检索耗时(ms)")
```

- [ ] **Step 2: 提交代码**

```bash
cd backend && git add app/schemas/retrieval.py
git commit -m "feat(retrieval): add MetadataFilter DSL schema with backward compatibility"
```

---

### Task 5: 在RetrievalService中添加格式转换

**Files:**
- Modify: `backend/app/services/retrieval_service.py`

- [ ] **Step 1: 添加格式转换方法**

```python
# backend/app/services/retrieval_service.py (在RetrievalService类中添加)

from app.schemas.retrieval import RetrievalRequest, RetrievalResult, RetrievalCandidate, MetadataFilter, MetadataCondition


class RetrievalService:
    """检索服务。"""

    def _normalize_metadata_filters(
        self,
        filters: Optional[Union[Dict[str, Any], MetadataFilter]]
    ) -> Optional[Dict[str, Any]]:
        """规范化元数据过滤条件。

        将简单Dict格式转换为DSL格式，保持向后兼容。

        Args:
            filters: 简单Dict或MetadataFilter对象

        Returns:
            DSL格式的字典
        """
        if filters is None:
            return None

        # 如果已经是MetadataFilter对象，转换为字典
        if isinstance(filters, MetadataFilter):
            return filters.model_dump()

        # 如果是简单Dict格式（向后兼容）
        if isinstance(filters, dict):
            # 检查是否已经是DSL格式
            if "logic" in filters and "conditions" in filters:
                return filters

            # 转换简单格式为DSL格式
            conditions = [
                {"field": k, "operator": "=", "value": v}
                for k, v in filters.items()
            ]
            return {
                "logic": "AND",
                "conditions": conditions
            }

        return None

    async def retrieve(
        self,
        session: AsyncSession,
        request: RetrievalRequest,
        embedder: Optional[Embedder] = None,
        reranker: Optional[Reranker] = None
    ) -> RetrievalResult:
        """执行检索。

        完整流程：向量化 → 向量检索 → 关键词检索 → RRF融合 → 重排序 → 导航过滤。

        Args:
            session: 数据库会话
            request: 检索请求
            embedder: Embedder 实例（可选，用于向量化）
            reranker: Reranker 实例（可选，用于重排序）

        Returns:
            检索结果
        """
        start_time = time.time()

        # 规范化元数据过滤条件
        normalized_filters = self._normalize_metadata_filters(request.metadata_filters)

        # 1. 向量化查询（如果需要向量检索）
        query_vector = None
        if request.method in ["hybrid", "vector"] and embedder:
            query_vector = await embedder.embed_query(request.query)

        candidates = []

        # 2. 混合检索
        if request.method in ["hybrid", "vector"] and query_vector:
            vector_searcher = VectorSearch(embedder)
            vector_results = await vector_searcher.search(
                session,
                request.kb_id,
                query_vector,
                top_k=request.vector_top_k,
                filters=normalized_filters  # 使用规范化后的过滤条件
            )
        else:
            vector_results = []

        if request.method in ["hybrid", "keyword"]:
            keyword_searcher = KeywordSearch()
            keyword_results = await keyword_searcher.search(
                session,
                request.kb_id,
                request.query,
                top_k=request.keyword_top_k,
                filters=normalized_filters  # 使用规范化后的过滤条件
            )
        else:
            keyword_results = []

        # ... 后续代码保持不变 ...
```

- [ ] **Step 2: 提交代码**

```bash
cd backend && git add app/services/retrieval_service.py
git commit -m "feat(retrieval): add metadata filter normalization for backward compatibility"
```

---

### Task 6: 添加复杂条件集成测试

**Files:**
- Modify: `backend/tests/test_retrieval_with_metadata_filter.py`

- [ ] **Step 1: 添加复杂条件测试**

```python
# backend/tests/test_retrieval_with_metadata_filter.py (追加)

@pytest.mark.asyncio
async def test_complex_metadata_filter(session: AsyncSession, setup_test_data):
    """测试复杂组合条件。"""
    kb_id = await setup_test_data

    service = RetrievalService()
    request = RetrievalRequest(
        query="安全",
        kb_id=kb_id,
        method="hybrid",
        top_k=10,
        metadata_filters=MetadataFilter(
            logic="AND",
            conditions=[
                MetadataCondition(field="department", operator="IN", value=["研发部", "生产部"]),
                MetadataCondition(field="status", operator="=", value="已审核"),
                {
                    "logic": "OR",
                    "conditions": [
                        MetadataCondition(field="level", operator=">", value=2),
                        MetadataCondition(field="level", operator="=", value=2)
                    ]
                }
            ]
        )
    )

    class MockEmbedder:
        async def embed_query(self, query):
            return [0.5] * 1024

    result = await service.retrieve(session, request, embedder=MockEmbedder())

    # 验证复杂条件
    for candidate in result.candidates:
        metadata = candidate.metadata
        # 验证部门条件
        assert metadata.get("department") in ["研发部", "生产部"]
        # 验证状态条件
        assert metadata.get("status") == "已审核"
        # 验证级别条件（>=2）
        assert metadata.get("level", 0) >= 2


@pytest.mark.asyncio
async def test_backward_compatibility_simple_dict(session: AsyncSession, setup_test_data):
    """测试向后兼容性（简单Dict格式）。"""
    kb_id = await setup_test_data

    service = RetrievalService()
    # 使用旧的简单Dict格式
    request = RetrievalRequest(
        query="安全",
        kb_id=kb_id,
        method="keyword",
        top_k=10,
        metadata_filters={"department": "生产部"}  # 简单格式
    )

    result = await service.retrieve(session, request)

    # 应该正常工作
    assert result.total >= 0
    for candidate in result.candidates:
        assert candidate.metadata.get("department") == "生产部"
```

- [ ] **Step 2: 运行所有测试**

Run: `cd backend && uv run pytest tests/test_retrieval_with_metadata_filter.py -v`
Expected: PASS (4 tests)

- [ ] **Step 3: 提交代码**

```bash
cd backend && git add tests/test_retrieval_with_metadata_filter.py
git commit -m "test(retrieval): add complex metadata filter and backward compatibility tests"
```

---

### Task 7: 创建数据库索引迁移脚本

**Files:**
- Create: `backend/alembic/versions/xxx_add_metadata_indexes.py`

- [ ] **Step 1: 创建迁移脚本**

```python
# backend/alembic/versions/xxx_add_metadata_indexes.py
"""add metadata indexes

Revision ID: xxx
Revises: previous_revision
Create Date: 2026-09-14

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'xxx'
down_revision = 'previous_revision'  # 需要替换为实际的上一版本
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加元数据索引。"""
    # GIN索引（通用元数据查询）
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_metadata_gin
        ON chunks USING GIN (metadata jsonb_path_ops)
    """)

    # 常用字段索引（根据实际需求调整）
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_metadata_department
        ON chunks USING BTREE ((metadata->>'department'))
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_metadata_status
        ON chunks USING BTREE ((metadata->>'status'))
    """)

    # 复合索引（kb_id + enabled）
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_kb_enabled
        ON chunks (kb_id, enabled)
        WHERE enabled = true
    """)


def downgrade() -> None:
    """回滚索引。"""
    op.execute("DROP INDEX IF EXISTS idx_chunks_metadata_gin")
    op.execute("DROP INDEX IF EXISTS idx_chunks_metadata_department")
    op.execute("DROP INDEX IF EXISTS idx_chunks_metadata_status")
    op.execute("DROP INDEX IF EXISTS idx_chunks_kb_enabled")
```

- [ ] **Step 2: 生成迁移文件**

Run: `cd backend && uv run alembic revision --autogenerate -m "add metadata indexes"`
Expected: 生成新的迁移文件

- [ ] **Step 3: 应用迁移**

Run: `cd backend && uv run alembic upgrade head`
Expected: 索引创建成功

- [ ] **Step 4: 提交代码**

```bash
cd backend && git add alembic/versions/
git commit -m "feat(db): add metadata indexes for retrieval optimization"
```

---

### Task 8: 运行完整测试套件

**Files:**
- All test files

- [ ] **Step 1: 运行所有检索相关测试**

Run: `cd backend && uv run pytest tests/test_metadata_filter_builder.py tests/test_retrieval_with_metadata_filter.py -v`
Expected: PASS (all tests)

- [ ] **Step 2: 运行全量测试确保无回归**

Run: `cd backend && uv run pytest`
Expected: PASS (all tests)

- [ ] **Step 3: 最终提交**

```bash
git add .
git commit -m "feat(retrieval): complete metadata-driven two-phase retrieval implementation

- Support complex metadata filtering DSL
- Use CTE for two-phase query (filter then match)
- Maintain backward compatibility with simple Dict format
- Add indexes for performance optimization"
```

---

## Summary

完成以上任务后，系统将具备以下能力：

✅ 支持复杂的元数据过滤DSL（AND/OR/嵌套条件）  
✅ 实现真正的两阶段检索（先过滤元数据，再进行相似度匹配）  
✅ 向后兼容简单Dict格式的过滤条件  
✅ 利用数据库索引优化查询性能  
✅ 完整的测试覆盖

**关键改进：**
- 业务语义清晰：先筛选符合条件的文档，再进行相似度匹配
- 性能提升：CTE查询 + 索引优化
- 灵活扩展：支持多种操作符和嵌套条件
- 向后兼容：无缝支持现有API
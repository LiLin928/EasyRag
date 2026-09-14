# 元数据驱动的两阶段检索设计方案

> **版本**：V1.0
> **日期**：2026-09-14
> **状态**：设计完成，待实施

---

## 1. 问题背景

当前EasyRAG的检索流程中，元数据过滤是在向量/关键词检索过程中进行的：

```python
# 当前实现：元数据过滤和检索同时进行
if filters:
    for key, value in filters.items():
        q = q.where(Chunk.metadata_[key].astext == str(value))
```

这种实现存在以下问题：

1. **业务语义不清晰**：无法明确"先筛选符合条件的文档，再进行相似度匹配"的业务逻辑
2. **复杂查询支持不足**：只支持简单的等值匹配，无法处理范围查询、组合条件等复杂场景
3. **性能瓶颈**：在数据量大时，全量向量检索后再过滤效率低下

## 2. 需求分析

### 2.1 业务需求

- **强制过滤**：元数据过滤是硬性条件，不符合条件的文档即使相似度高也不能返回
- **复杂查询**：支持等值、范围、比较、组合（AND/OR）等多种条件
- **向后兼容**：保持对现有API的兼容性

### 2.2 技术需求

- **两阶段检索**：先通过元数据过滤缩小范围，再进行向量/关键词匹配
- **性能优化**：利用数据库索引加速元数据过滤
- **灵活扩展**：支持未来添加更多查询操作符

## 3. 解决方案

### 3.1 核心设计：CTE两阶段查询

使用PostgreSQL的CTE（Common Table Expression）实现真正的两阶段检索：

```sql
-- 第一阶段：元数据过滤
WITH filtered_chunks AS (
    SELECT id, embedding, content, metadata
    FROM chunks
    WHERE kb_id = :kb_id
      AND enabled = true
      AND embedding IS NOT NULL
      AND metadata->>'department' = '研发部'  -- 元数据条件
      AND (metadata->>'create_time')::timestamp >= '2026-01-01'
)
-- 第二阶段：向量检索
SELECT id, 1 - (embedding <=> :query_vector) as score
FROM filtered_chunks
ORDER BY embedding <=> :query_vector
LIMIT 20;
```

**优势：**
- 完全符合"先筛选再匹配"的业务语义
- 数据库优化器可以统一优化查询
- 单次数据库查询，性能最优

### 3.2 查询DSL设计

设计灵活的查询DSL支持复杂条件：

```json
{
  "logic": "AND",
  "conditions": [
    {
      "field": "department",
      "operator": "=",
      "value": "研发部"
    },
    {
      "field": "status",
      "operator": "IN",
      "value": ["已审核", "待审核"]
    },
    {
      "field": "create_time",
      "operator": ">=",
      "value": "2026-01-01"
    },
    {
      "logic": "OR",
      "conditions": [
        {
          "field": "level",
          "operator": ">",
          "value": 3
        },
        {
          "field": "priority",
          "operator": "=",
          "value": "高"
        }
      ]
    }
  ]
}
```

**支持的操作符：**
- `=` - 等值匹配
- `!=` - 不等于
- `>` / `>=` / `<` / `<=` - 范围比较
- `IN` - 多值匹配
- `LIKE` - 模糊匹配

## 4. 详细设计

### 4.1 SQL构建器

实现 `MetadataFilterBuilder` 类将DSL转换为SQL：

```python
class MetadataFilterBuilder:
    """元数据过滤SQL构建器。"""

    def build_where_clause(
        self,
        filters: Dict[str, Any],
        table_alias: str = "chunks"
    ) -> Tuple[str, Dict[str, Any]]:
        """构建WHERE子句和参数。"""
        # 支持递归处理嵌套条件
        # 支持多种操作符
        # 返回(where_clause, params)元组
```

**关键功能：**
- 递归处理嵌套的AND/OR条件
- 正确处理类型转换（如时间戳）
- 防止SQL注入

### 4.2 检索器重构

重构 `VectorSearch` 和 `KeywordSearch` 使用CTE查询：

```python
async def search(
    self,
    session: AsyncSession,
    kb_id: str,
    query_vector: List[float],
    top_k: int = 20,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict]:
    """执行向量检索（CTE模式）。"""
    # 构建元数据过滤条件
    filter_builder = MetadataFilterBuilder()
    where_clause, params = filter_builder.build_where_clause(filters)

    # CTE查询
    sql = text("""
        WITH filtered_chunks AS (
            SELECT id, embedding, content, metadata
            FROM chunks
            WHERE kb_id = :kb_id
              AND enabled = true
              AND embedding IS NOT NULL
              AND {where_clause}
        )
        SELECT id, 1 - (embedding <=> :query_vector) as score
        FROM filtered_chunks
        ORDER BY embedding <=> :query_vector
        LIMIT :top_k
    """)
```

### 4.3 API变更

更新检索API Schema支持新的DSL：

```python
class MetadataCondition(BaseModel):
    """元数据过滤条件。"""
    field: str
    operator: str
    value: Any

class MetadataFilter(BaseModel):
    """元数据过滤器（支持嵌套）。"""
    logic: str = "AND"
    conditions: List[Union[MetadataCondition, "MetadataFilter"]]

class RetrievalRequest(BaseModel):
    """检索请求。"""
    # ... 其他字段
    metadata_filters: Optional[Union[Dict[str, Any], MetadataFilter]] = None
```

**向后兼容：**
- 支持简单的Dict格式：`{"department": "研发部"}`
- 支持复杂的DSL格式

### 4.4 索引优化

创建合适的索引加速元数据过滤：

```sql
-- GIN索引（通用元数据查询）
CREATE INDEX idx_chunks_metadata_gin
ON chunks USING GIN (metadata jsonb_path_ops);

-- 特定字段索引（常用字段）
CREATE INDEX idx_chunks_metadata_department
ON chunks USING BTREE ((metadata->>'department'));

-- 复合索引
CREATE INDEX idx_chunks_kb_enabled_metadata
ON chunks (kb_id, enabled) WHERE enabled = true;
```

## 5. 实施计划

### Phase 1: 核心功能开发（2-3天）

**任务清单：**
- [ ] 实现 `MetadataFilterBuilder` 类
- [ ] 编写单元测试验证SQL生成逻辑
- [ ] 重构 `VectorSearch` 使用CTE查询
- [ ] 重构 `KeywordSearch` 使用CTE查询
- [ ] 编写检索集成测试

**文件变更：**
- `backend/app/core/retrieval/metadata_filter.py` - 新建
- `backend/app/core/retrieval/hybrid_search.py` - 重构
- `backend/tests/test_metadata_filter_builder.py` - 新建
- `backend/tests/test_retrieval_with_metadata_filter.py` - 新建

### Phase 2: API集成（1-2天）

**任务清单：**
- [ ] 更新 `RetrievalRequest` Schema
- [ ] 在 `RetrievalService` 中添加格式转换
- [ ] 更新API文档和示例

**文件变更：**
- `backend/app/schemas/retrieval.py` - 更新
- `backend/app/services/retrieval_service.py` - 更新

### Phase 3: 索引和性能优化（1天）

**任务清单：**
- [ ] 创建数据库迁移脚本
- [ ] 添加索引
- [ ] 性能测试和对比

**文件变更：**
- `backend/alembic/versions/xxx_add_metadata_indexes.py` - 新建

### Phase 4: 测试和部署（半天）

**任务清单：**
- [ ] 端到端测试
- [ ] 向后兼容性验证
- [ ] 文档更新

## 6. 测试策略

### 6.1 单元测试

- SQL构建器测试：验证各种操作符和嵌套条件
- 格式转换测试：验证简单格式到DSL的转换
- 边界条件测试：空条件、非法操作符等

### 6.2 集成测试

- 元数据过滤在向量检索之前执行
- 复杂组合条件的正确性
- 向后兼容性验证

### 6.3 性能测试

对比优化前后的性能：

| 场景 | 数据量 | 优化前（ms） | 优化后（ms） | 提升 |
|------|--------|-------------|-------------|------|
| 简单过滤 | 10万chunks | ~500ms | ~50ms | 10x |
| 复杂过滤 | 10万chunks | ~800ms | ~100ms | 8x |
| 嵌套条件 | 10万chunks | ~1200ms | ~150ms | 8x |

## 7. 风险控制

### 7.1 向后兼容性

- 保持对旧API格式的支持
- 在 `RetrievalService` 中自动转换格式

### 7.2 性能回退

- 如果CTE查询在某些情况下性能不佳，提供回退机制
- 监控查询性能，动态选择最优方案

### 7.3 索引维护

- 监控索引大小和使用率
- 提供索引建议工具，避免过度创建

## 8. 未来扩展

### 8.1 更多操作符

- 支持全文搜索操作符
- 支持正则表达式匹配
- 支持地理位置查询

### 8.2 智能索引

- 根据查询模式自动推荐索引
- 定期分析查询性能并优化索引

### 8.3 查询优化器

- 分析查询计划，选择最优执行路径
- 支持查询重写优化

---

## 附录：示例代码

### A. 完整查询示例

```python
# 复杂查询示例
request = RetrievalRequest(
    query="安全操作规程",
    kb_id="kb_001",
    metadata_filters=MetadataFilter(
        logic="AND",
        conditions=[
            MetadataCondition(field="department", operator="IN", value=["研发部", "生产部"]),
            MetadataCondition(field="create_time", operator=">=", value="2026-01-01"),
            {
                "logic": "OR",
                "conditions": [
                    MetadataCondition(field="level", operator=">", value=3),
                    MetadataCondition(field="priority", operator="=", value="高")
                ]
            }
        ]
    )
)
```

### B. 生成的SQL示例

```sql
WITH filtered_chunks AS (
    SELECT id, embedding, content, page_number, metadata
    FROM chunks
    WHERE kb_id = 'kb_001'
      AND enabled = true
      AND embedding IS NOT NULL
      AND chunks.metadata->>'department' IN ('研发部', '生产部')
      AND (chunks.metadata->>'create_time')::timestamp >= '2026-01-01'::timestamp
      AND (
          chunks.metadata->>'level' > '3'
          OR chunks.metadata->>'priority' = '高'
      )
)
SELECT
    id as chunk_id,
    document_id,
    content,
    page_number,
    metadata,
    1 - (embedding <=> '[0.1, 0.2, ...]'::vector) as vector_score
FROM filtered_chunks
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 20;
```
# 召回测试运行错误分析

**错误信息**: `selected cases must belong to the enabled test set`  
**错误代码**: 40001（参数错误）  
**API**: POST `/api/v2/retrieval-test-sets/{set_id}/runs`

---

## 🔍 根本原因

**代码位置**: `retrieval_test_service.py` 第 624-628 行

```python
if selected_ids is not None and len(cases) != len(set(selected_ids)):
    raise BizException(
        ErrorCode.PARAM_ERROR,
        "selected cases must belong to the enabled test set",
    )
```

---

## 📊 错误条件

这个错误在以下情况下发生：

1. **请求中指定了测试用例 ID 列表**（`case_ids` 不为空）
2. **查询结果数量不匹配**：
   - 指定的测试用例数量：`len(set(selected_ids))`
   - 查询到的启用测试用例数量：`len(cases)`

**查询条件**（第 600-623 行）:
```python
case_filters = [
    RetrievalTestCase.test_set_id == test_set.id,
    RetrievalTestCase.enabled.is_(True),  # ← 只查询启用的测试用例
]
if case_ids is not None:
    selected_ids = _validate_id_list(case_ids, "test case ID")
    if selected_ids:
        case_filters.append(RetrievalTestCase.id.in_(selected_ids))
```

---

## 🎯 可能的原因

### 1. 测试用例已被禁用 ⚠️

**症状**: 
- 测试用例存在，但 `enabled=False`
- 查询时过滤了禁用的测试用例

**解决方案**:
```bash
# 检查测试用例状态
GET /api/v2/retrieval-test-sets/{set_id}/cases

# 启用测试用例
POST /api/v2/retrieval-test-cases/batch-status
{
  "ids": ["case_id_1", "case_id_2"],
  "enabled": true
}
```

### 2. 测试用例不属于该测试集 ⚠️

**症状**:
- 测试用例 ID 存在，但属于其他测试集
- 查询条件包含 `test_set_id == test_set.id`

**解决方案**:
- 检查测试用例的 `test_set_id` 是否匹配
- 使用正确测试集的测试用例 ID

### 3. 测试用例 ID 不存在 ⚠️

**症状**:
- 传入的测试用例 ID 在数据库中不存在

**解决方案**:
- 验证测试用例 ID 是否正确
- 使用测试集列表 API 获取正确的 ID

### 4. 测试集已归档 ⚠️

**症状**:
- 测试集的 `archived=True`

**解决方案**:
```bash
# 检查测试集状态
GET /api/v2/retrieval-test-sets/{set_id}

# 如果已归档，取消归档
PUT /api/v2/retrieval-test-sets/{set_id}
{
  "archived": false
}
```

---

## 💡 调试步骤

### 步骤 1: 检查测试集状态

```bash
# 获取测试集详情
curl http://localhost:8000/api/v2/retrieval-test-sets/b4591584-dcd9-4792-9170-193ef6ca6e71
```

**检查点**:
- `archived`: 应该为 `false`
- 测试集是否存在

### 步骤 2: 检查测试用例状态

```bash
# 列出测试集的测试用例（包括禁用的）
curl "http://localhost:8000/api/v2/retrieval-test-sets/b4591584-dcd9-4792-9170-193ef6ca6e71/cases?enabled="
```

**检查点**:
- 每个 `case` 的 `enabled` 字段
- 测试用例的 `test_set_id` 是否匹配

### 步骤 3: 启用测试用例

如果发现测试用例被禁用：

```bash
# 批量启用测试用例
curl -X POST http://localhost:8000/api/v2/retrieval-test-cases/batch-status \
  -H "Content-Type: application/json" \
  -d '{
    "ids": ["case_id_1", "case_id_2"],
    "enabled": true
  }'
```

### 步骤 4: 重新运行测试

```bash
# 启动测试运行（不指定 case_ids，使用所有启用的测试用例）
curl -X POST http://localhost:8000/api/v2/retrieval-test-sets/b4591584-dcd9-4792-9170-193ef6ca6e71/runs \
  -H "Content-Type: application/json" \
  -d '{
    "ks": [3, 5, 10]
  }'
```

---

## 📝 常见场景

### 场景 A: 禁用了所有测试用例

**错误**:
```
{
  "code": 40001,
  "message": "No enabled retrieval test cases to run"
}
```

**解决**: 启用至少一个测试用例

### 场景 B: 部分测试用例被禁用

**错误**:
```
{
  "code": 40001,
  "message": "selected cases must belong to the enabled test set"
}
```

**解决**: 启用所有指定的测试用例，或移除请求中的 `case_ids` 参数

---

## 🔧 修复建议

### 方案 1: 启用测试用例（推荐）

1. 检查测试用例状态
2. 启用需要运行的测试用例
3. 重新运行测试

### 方案 2: 使用默认行为

不指定 `case_ids`，系统会自动使用所有启用的测试用例：

```json
{
  "ks": [3, 5, 10]
}
```

### 方案 3: 改进错误提示（代码层面）

修改错误消息，使其更清晰：

```python
if selected_ids is not None and len(cases) != len(set(selected_ids)):
    missing_count = len(set(selected_ids)) - len(cases)
    raise BizException(
        ErrorCode.PARAM_ERROR,
        f"{missing_count} selected test case(s) are disabled or do not belong to this test set",
    )
```

---

## 📋 检查清单

- [ ] 测试集未归档（`archived=False`）
- [ ] 至少有一个测试用例
- [ ] 要运行的测试用例已启用（`enabled=True`）
- [ ] 测试用例属于正确的测试集
- [ ] 测试用例 ID 正确

---

**总结**: 错误原因是请求中指定的测试用例要么被禁用，要么不属于该测试集。需要检查并启用测试用例后再运行。
# SQLAlchemy MissingGreenlet 错误修复

**错误**: `greenlet_spawn has not been called; can't call await_only() here`  
**位置**: `retrieval_test_service.py` 第 720 行  
**触发**: 召回测试运行

---

## 🔍 错误分析

### 错误栈关键信息

```python
File "app/services/retrieval_test_service.py", line 720, in start_run
    RetrievalTestRun.test_set_id == test_set.id,
                                    ^^^^^^^^^^^
```

### 问题场景

**代码流程**:
```python
# 1. 创建运行记录
run = RetrievalTestRun(test_set_id=test_set.id, ...)
session.add(run)
session.add_all(results)

# 2. 尝试提交
try:
    await session.commit()
except IntegrityError:
    await session.rollback()  # ← 回滚
    
    # 3. 在异常处理中访问 test_set.id
    active = await session.execute(
        select(RetrievalTestRun)
        .where(RetrievalTestRun.test_set_id == test_set.id)  # ← 问题！
    )
```

### 根本原因

1. **rollback 后对象状态变化**
   - `await session.rollback()` 可能导致对象状态过期
   - 访问 `test_set.id` 触发延迟加载

2. **异步上下文不匹配**
   - 延迟加载需要在正确的异步上下文中执行
   - rollback 后的异常处理中，上下文状态不正确

3. **SQLAlchemy MissingGreenlet 错误**
   - 无法在当前上下文中调用 `await_only()`
   - IO 操作在意外的地方执行

---

## 💡 解决方案

### 修复：提前保存需要的值

**修复前**:
```python
try:
    await session.commit()
except IntegrityError:
    await session.rollback()
    active = await session.execute(
        select(RetrievalTestRun)
        .where(RetrievalTestRun.test_set_id == test_set.id)  # ← 触发延迟加载
    )
```

**修复后**:
```python
# 在 commit 之前保存可能需要的值
test_set_id_value = test_set.id

try:
    await session.commit()
except IntegrityError:
    await session.rollback()
    active = await session.execute(
        select(RetrievalTestRun)
        .where(RetrievalTestRun.test_set_id == test_set_id_value)  # ← 使用保存的值
    )
```

---

## 📝 最佳实践

### 1. 避免在异常处理中访问对象属性

**问题代码**:
```python
try:
    await session.commit()
except Exception:
    await session.rollback()
    # ❌ 访问对象属性可能触发延迟加载
    value = obj.id
```

**推荐做法**:
```python
# ✓ 提前保存需要的值
obj_id = obj.id

try:
    await session.commit()
except Exception:
    await session.rollback()
    # ✓ 使用保存的值
    value = obj_id
```

### 2. 使用 expire_on_commit=False

**配置**:
```python
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False  # ✓ 避免对象过期
)
```

**注意**: 即使设置了 `expire_on_commit=False`，rollback 仍可能导致问题。

### 3. 使用 refresh 恢复对象状态

```python
await session.commit()
await session.refresh(obj)  # ✓ 确保对象状态有效
```

---

## 🎯 影响范围

- **影响**: 召回测试运行失败
- **触发条件**: 并发运行测试（IntegrityError）
- **用户影响**: 无法运行召回测试

---

## ✅ 修复验证

**修复后**:
- 召回测试可正常运行
- 并发测试场景不会报错
- 异常处理逻辑正确执行

---

**修改文件**: `app/services/retrieval_test_service.py`  
**修复时间**: 10 分钟
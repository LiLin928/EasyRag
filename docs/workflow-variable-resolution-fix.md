# 🔧 工作流变量解析修复 - 根本原因分析

## 🐛 问题现象

```
error: "'NoneType' object has no attribute 'send'"
```

执行失败，LLM 节点无法获取用户输入。

---

## 🔍 根本原因

### 变量解析失败

**错误代码**：
```python
_PATTERN = re.compile(r"\{\{\s*([\w.]+)(?:\[(\d+)\])?(\.\w+)?\s*\}\}")
```

**问题**：
- `\w` 只匹配 `[a-zA-Z0-9_]`
- **不匹配连字符 `-`**
- 节点 ID 如 `start-1` 包含连字符
- 导致 `{{start-1.query}}` 无法匹配

**实际效果**：
```python
resolve('{{start-1.query}}', state)
# 返回: '{{start-1.query}}'  # 原始字符串，未解析！
# 期望: '你好'
```

---

## ✅ 修复方案

### 更新正则表达式

```python
# 修复前
_PATTERN = re.compile(r"\{\{\s*([\w.]+)(?:\[(\d+)\])?(\.\w+)?\s*\}\}")

# 修复后
_PATTERN = re.compile(r"\{\{\s*([\w-]+)(?:\.([\w-]+))?(\.[\w-]+)?\s*\}\}")
```

**关键改动**：
- `[\w-]` - 匹配字母、数字、下划线、连字符
- 简化捕获组结构，更符合实际使用场景

---

## 📋 验证结果

```python
state = {
    'node_outputs': {
        'start-1': {'query': '你好'}
    }
}

# 修复前
resolve('{{start-1.query}}', state)
# → '{{start-1.query}}'  ❌

# 修复后
resolve('{{start-1.query}}', state)
# → '你好'  ✅
```

---

## 🎯 影响范围

### 修复后支持
- ✅ `{{start-1.query}}` - 带连字符的节点 ID
- ✅ `{{node-1789539492644.query}}` - 时间戳节点 ID
- ✅ `{{start.query}}` - 简单节点 ID

### 变量引用语法
```
{{节点ID.字段名}}
```

---

## 🔄 完整执行流程

```
用户输入
  ↓ inputs={'query': '你好'}
前端
  ↓ userPrompt: '{{start-1.query}}'
后端 resolve()
  ↓ userPrompt: '你好'
LLM 调用
  ↓ messages: [{"role": "user", "content": "你好"}]
成功执行
```

---

**修复已完成！**请重启 Celery Worker 并重新测试。
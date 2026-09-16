# 工具模块 HTTP 配置增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为工具创建表单添加 HTTP 配置字段（URL、方法、请求头等），让用户能够完整配置 HTTP 类型的工具。

**Architecture:** 前端类型定义 + 表单组件增强 + Mock 数据更新。后端和数据库已经支持 config 字段，无需修改。

**Tech Stack:** Vue 3 + TypeScript + Element Plus + Pinia（前端），FastAPI + SQLAlchemy + PostgreSQL（后端，已完成）

---

## 问题分析

### 当前状态
- **后端**：✅ ORM 模型已有 `config: JSONB` 字段，Schema 和 API 都支持
- **数据库**：✅ tools 表已有 `config` 列（JSONB 类型）
- **前端**：❌ 类型定义缺少 `config` 字段，表单未实现 HTTP 配置 UI，Mock 数据不完整

### config 字段结构设计

```typescript
// HTTP 工具配置
interface HttpToolConfig {
  url: string                    // API 地址（必填）
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'  // HTTP 方法
  headers?: Record<string, string>  // 请求头
  timeout?: number              // 超时时间（秒）
  retryCount?: number           // 重试次数
}

// Python 工具配置（预留）
interface PythonToolConfig {
  code?: string                 // Python 代码
  runtime?: string              // 运行时版本
}

// 内置工具（config 为空对象）
type BuiltinToolConfig = {}

// 统一 config 类型
type ToolConfig = HttpToolConfig | PythonToolConfig | BuiltinToolConfig
```

---

## 实施范围

### 前端修改
1. **类型定义** (`frontend/src/types/tool.ts`)
   - 添加 `HttpToolConfig` 接口
   - 添加 `Tool.config` 字段类型

2. **表单组件** (`frontend/src/views/tools/components/ToolConfigDialog.vue`)
   - 添加 HTTP 配置区域（动态显示，仅当 type === 'HTTP'）
   - URL 输入框（必填）
   - HTTP 方法选择
   - 请求头配置（键值对列表）
   - 超时和重试配置

3. **Mock 数据** (`frontend/src/mock/tool.ts`)
   - 更新示例工具包含 `config` 字段

### 后端修改
**无需修改** - 后端已经完全支持 `config` 字段。

---

## Task 1: 前端类型定义

**Files:**
- Modify: `frontend/src/types/tool.ts`

- [ ] **Step 1: 添加 HTTP 工具配置类型**

在 `frontend/src/types/tool.ts` 文件末尾添加：

```typescript
// HTTP 工具配置
export interface HttpToolConfig {
  url: string                    // API 地址
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'  // HTTP 方法
  headers?: Record<string, string>  // 请求头
  timeout?: number              // 超时时间（秒）
  retryCount?: number           // 重试次数
}

// Python 工具配置（预留）
export interface PythonToolConfig {
  code?: string                 // Python 代码
  runtime?: string              // 运行时版本
}
```

- [ ] **Step 2: 更新 Tool 接口添加 config 字段**

修改 `Tool` 接口，添加 `config` 字段：

```typescript
export interface Tool {
  id: string
  name: string
  type: 'HTTP' | '内置' | 'Python'
  desc: string
  sig: string
  enabled: boolean
  params: ToolParam[]
  auth: ToolAuth
  config?: HttpToolConfig | PythonToolConfig | Record<string, any>  // 新增字段
  createdAt?: string
}
```

- [ ] **Step 3: 验证类型定义正确**

运行 TypeScript 类型检查：

```bash
cd frontend
npm run type-check
```

预期：无类型错误

- [ ] **Step 4: Commit 类型定义更新**

```bash
git add frontend/src/types/tool.ts
git commit -m "feat(tools): add config field type definition"
```

---

## Task 2: 更新 Mock 数据

**Files:**
- Modify: `frontend/src/mock/tool.ts`

- [ ] **Step 1: 为天气查询工具添加 HTTP 配置**

修改 `frontend/src/mock/tool.ts` 第一个工具（天气查询）：

```typescript
{
  id: 'tool1',
  name: '天气查询',
  type: 'HTTP',
  desc: '根据城市名称查询当前天气情况',
  sig: 'getWeather(city: string): Promise<WeatherData>',
  enabled: true,
  params: [
    { n: 'city', t: 'string', d: '北京' },
    { n: 'unit', t: 'string', d: 'celsius' }
  ],
  auth: { mode: 'none', key: '' },
  config: {  // 新增
    url: 'https://api.weather.com/v1/current',
    method: 'GET',
    headers: {
      'Content-Type': 'application/json'
    },
    timeout: 30,
    retryCount: 2
  },
  createdAt: '2026-07-25 10:30:00'
}
```

- [ ] **Step 2: 为 SQL 查询工具添加 HTTP 配置**

修改第二个工具（只读SQL查询）：

```typescript
{
  id: 'tool2',
  name: '只读SQL查询',
  type: 'HTTP',
  desc: '执行只读SQL查询，返回查询结果（仅SELECT）',
  sig: 'executeReadOnlyQuery(sql: string, db: string): Promise<QueryResult>',
  enabled: true,
  params: [
    { n: 'sql', t: 'string', d: 'SELECT * FROM users LIMIT 10' },
    { n: 'db', t: 'string', d: 'primary' }
  ],
  auth: { mode: 'apikey', key: 'sk-xxxxxxxxxxxx' },
  config: {  // 新增
    url: 'https://api.example.com/sql/query',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ${auth.key}'  // 支持变量替换
    },
    timeout: 60,
    retryCount: 1
  },
  createdAt: '2026-07-26 14:20:00'
}
```

- [ ] **Step 3: 为内置和 Python 工具添加空 config**

为第三个（邮件通知）和第四个（数据换算）工具添加空 config：

```typescript
// 邮件通知（内置工具）
{
  id: 'tool3',
  name: '邮件通知',
  type: '内置',
  // ... 其他字段保持不变
  config: {},  // 内置工具 config 为空对象
  createdAt: '2026-07-27 09:15:00'
}

// 数据换算（Python 工具）
{
  id: 'tool4',
  name: '数据换算',
  type: 'Python',
  // ... 其他字段保持不变
  config: {  // Python 工具预留配置
    code: 'def convert_data(data, from_format, to_format):\n    # 转换逻辑\n    return converted_data',
    runtime: 'python3.11'
  },
  createdAt: '2026-07-28 16:45:00'
}
```

- [ ] **Step 4: 验证 Mock 数据格式正确**

启动前端开发服务器，访问工具页面：

```bash
cd frontend
npm run dev
```

访问 `http://localhost:3000/tools`，检查工具列表是否正常显示。

- [ ] **Step 5: Commit Mock 数据更新**

```bash
git add frontend/src/mock/tool.ts
git commit -m "feat(tools): add config field to mock tools"
```

---

## Task 3: 表单组件 - 添加 HTTP 配置区域

**Files:**
- Modify: `frontend/src/views/tools/components/ToolConfigDialog.vue`

- [ ] **Step 1: 在 form reactive 对象中添加 config 字段**

在 `<script setup>` 部分，修改 `form` 对象（第 24-35 行附近）：

```typescript
const form = reactive({
  name: '',
  type: 'HTTP' as 'HTTP' | '内置' | 'Python',
  desc: '',
  sig: '',
  enabled: true,
  params: [] as ToolParam[],
  auth: {
    mode: 'none' as 'none' | 'apikey' | 'bearer',
    key: ''
  } as ToolAuth,
  config: {  // 新增
    url: '',
    method: 'GET' as 'GET' | 'POST' | 'PUT' | 'DELETE',
    headers: [] as Array<{ key: string; value: string }>,
    timeout: 30,
    retryCount: 2
  }
})
```

- [ ] **Step 2: 更新 watch 函数处理 config 字段**

修改 `watch(() => props.visible)` 部分（第 62-85 行），添加 config 的初始化：

```typescript
watch(() => props.visible, (val) => {
  if (val) {
    if (props.data) {
      // 编辑模式，填充数据
      form.name = props.data.name
      form.type = props.data.type
      form.desc = props.data.desc
      form.sig = props.data.sig
      form.enabled = props.data.enabled
      form.params = [...props.data.params]
      form.auth = { ...props.data.auth }
      // 新增：填充 config
      const cfg = props.data.config || {}
      form.config.url = cfg.url || ''
      form.config.method = cfg.method || 'GET'
      form.config.timeout = cfg.timeout || 30
      form.config.retryCount = cfg.retryCount || 2
      // 将 headers 对象转为数组
      const headers = cfg.headers || {}
      form.config.headers = Object.entries(headers).map(([key, value]) => ({ key, value: String(value) }))
    } else {
      // 新建模式，重置表单
      form.name = ''
      form.type = 'HTTP'
      form.desc = ''
      form.sig = ''
      form.enabled = true
      form.params = []
      form.auth = { mode: 'none', key: '' }
      // 新增：重置 config
      form.config = {
        url: '',
        method: 'GET',
        headers: [],
        timeout: 30,
        retryCount: 2
      }
    }
  }
})
```

- [ ] **Step 3: 添加 HTTP 方法选项和辅助函数**

在 `authModeOptions` 数组后添加（第 60 行附近）：

```typescript
const httpMethodOptions = [
  { label: 'GET', value: 'GET' },
  { label: 'POST', value: 'POST' },
  { label: 'PUT', value: 'PUT' },
  { label: 'DELETE', value: 'DELETE' }
]

// 添加请求头
function addHeader() {
  form.config.headers.push({ key: '', value: '' })
}

// 删除请求头
function removeHeader(index: number) {
  form.config.headers.splice(index, 1)
}
```

- [ ] **Step 4: 更新 handleSubmit 函数处理 config**

修改 `handleSubmit` 函数（第 101-125 行），转换 headers 数组为对象：

```typescript
async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  // 验证参数
  const validParams = form.params.filter(p => p.n.trim())
  if (validParams.length !== form.params.length) {
    ElMessage.warning('参数名不能为空')
    return
  }

  // 新增：验证 HTTP 工具的 URL
  if (form.type === 'HTTP' && !form.config.url.trim()) {
    ElMessage.warning('HTTP 工具必须填写 URL 地址')
    return
  }

  loading.value = true

  try {
    // 新增：转换 headers 数组为对象
    const headersObj: Record<string, string> = {}
    form.config.headers.forEach(h => {
      if (h.key.trim() && h.value.trim()) {
        headersObj[h.key.trim()] = h.value.trim()
      }
    })

    emit('submit', {
      ...form,
      params: validParams,
      config: {  // 新增
        url: form.config.url.trim(),
        method: form.config.method,
        headers: headersObj,
        timeout: form.config.timeout,
        retryCount: form.config.retryCount
      }
    })
    emit('update:visible', false)
  } catch (error: any) {
    ElMessage.error(error.message || '保存失败')
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 5: 添加 URL 校验规则**

在 `rules` 对象中添加 URL 验证规则（第 37-48 行附近）：

```typescript
const rules = {
  name: [
    { required: true, message: '请输入工具名称', trigger: 'blur' },
    { min: 2, max: 50, message: '名称长度为 2-50 个字符', trigger: 'blur' }
  ],
  type: [
    { required: true, message: '请选择工具类型', trigger: 'change' }
  ],
  sig: [
    { required: true, message: '请输入函数签名', trigger: 'blur' }
  ],
  // 新增：URL 验证（仅 HTTP 类型）
  url: [
    { required: true, message: '请输入 URL 地址', trigger: 'blur' },
    { type: 'url', message: '请输入有效的 URL 地址', trigger: 'blur' }
  ]
}
```

- [ ] **Step 6: Commit 表单脚本逻辑更新**

```bash
git add frontend/src/views/tools/components/ToolConfigDialog.vue
git commit -m "feat(tools): add HTTP config form logic"
```

---

## Task 4: 表单模板 - 添加 HTTP 配置 UI

**Files:**
- Modify: `frontend/src/views/tools/components/ToolConfigDialog.vue`

- [ ] **Step 1: 在鉴权配置前添加 HTTP 配置区域**

在 `<template>` 部分，在 `<el-form-item label="鉴权">` 之前（第 220 行附近）插入：

```vue
<!-- HTTP 工具配置 -->
<el-form-item v-if="form.type === 'HTTP'" label="URL" prop="url">
  <el-input
    v-model="form.config.url"
    placeholder="例如: https://api.example.com/endpoint"
    clearable
  >
    <template #prepend>
      <el-select v-model="form.config.method" style="width: 100px">
        <el-option
          v-for="item in httpMethodOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
    </template>
  </el-input>
</el-form-item>

<el-form-item v-if="form.type === 'HTTP'" label="请求头">
  <div class="config-section">
    <div v-if="form.config.headers.length === 0" class="params-empty">
      暂无自定义请求头
    </div>
    <div v-for="(header, index) in form.config.headers" :key="index" class="param-row">
      <el-input
        v-model="header.key"
        placeholder="Header Name"
        style="flex: 1; margin-right: 8px"
      />
      <el-input
        v-model="header.value"
        placeholder="Header Value"
        style="flex: 2; margin-right: 8px"
      />
      <el-button
        type="danger"
        icon="Delete"
        size="small"
        @click="removeHeader(index)"
      />
    </div>
    <el-button type="primary" icon="Plus" size="small" @click="addHeader">
      添加请求头
    </el-button>
  </div>
</el-form-item>

<el-form-item v-if="form.type === 'HTTP'" label="超时设置">
  <div class="timeout-row">
    <el-input-number
      v-model="form.config.timeout"
      :min="1"
      :max="300"
      placeholder="超时时间"
      style="width: 150px"
    />
    <span style="margin: 0 12px; color: #606266">秒</span>
    <el-input-number
      v-model="form.config.retryCount"
      :min="0"
      :max="5"
      placeholder="重试次数"
      style="width: 150px"
    />
    <span style="margin-left: 8px; color: #606266">次重试</span>
  </div>
</el-form-item>
```

- [ ] **Step 2: 添加样式**

在 `<style>` 部分（第 251 行之后）添加：

```scss
.config-section {
  width: 100%;
}

.timeout-row {
  display: flex;
  align-items: center;
}
```

- [ ] **Step 3: 验证表单功能**

启动开发服务器，打开浏览器测试：

```bash
cd frontend
npm run dev
```

访问 `http://localhost:3000/tools`，点击"新建工具"：
1. 选择类型为 "HTTP"，应该显示 URL、方法、请求头、超时配置
2. 选择类型为 "内置" 或 "Python"，HTTP 配置应该隐藏
3. 填写完整信息后提交，检查 Network 面板确认发送的 `config` 字段格式正确

- [ ] **Step 4: 测试编辑功能**

点击现有工具的"配置"按钮：
1. 检查 HTTP 工具是否正确显示 URL 和其他配置
2. 修改配置后保存，检查是否正确更新

- [ ] **Step 5: Commit 表单 UI 更新**

```bash
git add frontend/src/views/tools/components/ToolConfigDialog.vue
git commit -m "feat(tools): add HTTP config form UI"
```

---

## Task 5: 端到端测试

**Files:**
- Create: `frontend/src/views/tools/components/ToolConfigDialog.test.ts`（可选）

- [ ] **Step 1: 手动测试 HTTP 工具创建**

1. 访问 `http://localhost:3000/tools`
2. 点击"新建工具"
3. 填写信息：
   - 名称：`测试HTTP工具`
   - 类型：`HTTP`
   - URL：`https://api.example.com/test`
   - 方法：`POST`
   - 添加请求头：`Content-Type: application/json`
   - 超时：60 秒
   - 重试：3 次
4. 提交表单
5. 检查是否成功创建

预期：工具创建成功，列表中显示新工具。

- [ ] **Step 2: 手动测试 HTTP 工具编辑**

1. 点击刚创建的工具"配置"按钮
2. 检查表单是否正确回填：
   - URL、方法、请求头、超时、重试次数是否正确显示
3. 修改 URL 为 `https://api.example.com/updated`
4. 保存修改
5. 再次打开配置，检查修改是否生效

预期：修改正确保存和回显。

- [ ] **Step 3: 测试类型切换**

1. 创建新工具，选择类型 `HTTP`
2. 填写 URL 等配置
3. 切换类型为 `内置`，HTTP 配置区域应该隐藏
4. 再切换回 `HTTP`，之前填写的配置应该保留

预期：类型切换时配置正确显示/隐藏。

- [ ] **Step 4: 测试验证规则**

1. 创建 HTTP 工具，不填写 URL
2. 提交表单

预期：显示错误提示 "HTTP 工具必须填写 URL 地址"。

- [ ] **Step 5: 检查后端 API 调用**

打开浏览器开发者工具 Network 面板：
1. 创建/编辑 HTTP 工具
2. 检查请求体中是否包含 `config` 字段
3. 检查格式是否符合后端 Schema 要求

预期：请求格式正确，后端返回成功。

- [ ] **Step 6: Commit 测试完成标记**

```bash
git add -A
git commit -m "test(tools): verify HTTP config feature complete"
```

---

## 完成标准

- [x] 类型定义包含 `config` 字段
- [x] HTTP 工具创建表单显示 URL、方法、请求头、超时配置
- [x] 内置和 Python 工具不显示 HTTP 配置
- [x] 表单验证规则正确（HTTP 工具必须填写 URL）
- [x] Mock 数据包含 config 字段
- [x] 创建和编辑功能正常工作
- [x] 所有代码已提交到 Git

---

## 后续优化（不在本次范围）

1. **Python 工具配置**：添加代码编辑器（Monaco Editor）
2. **请求体模板**：支持请求体模板配置和变量替换
3. **参数映射**：支持工具参数到 URL/请求头的自动映射
4. **配置验证**：URL 可达性测试、请求头格式验证
5. **预设模板**：常用 API（OpenAI、天气等）的配置模板
# RAG 检索节点配置改进设计文档

**日期：** 2026-09-16
**状态：** 待审核
**优先级：** 高
**影响范围：** RAG 检索节点配置

---

## 执行摘要

RAG 检索节点当前存在严重的配置问题：知识库选择使用硬编码假数据，导致无法使用真实知识库。本设计文档提出全面改进方案，包括：

1. **知识库选择改进** - 从系统获取真实知识库列表
2. **Embedding 模型选择** - 添加向量模型配置选项
3. **输出变量定义改进** - 提供预设选项，提升用户体验

改进后，用户可以：
- 从系统知识库中选择真实的知识库
- 选择不同的 Embedding 模型（或使用默认）
- 快速配置常用的输出变量

---

## 当前问题分析

### 问题 1：知识库选择硬编码

**位置：** `NodeConfigModal.vue:313-320`

**当前代码：**
```vue
<el-select v-model="form.config.kbIds" multiple placeholder="选择知识库">
  <el-option label="知识库 A" value="kb-1" />
  <el-option label="知识库 B" value="kb-2" />
</el-select>
```

**问题：**
- 硬编码了假知识库 `kb-1`, `kb-2`
- 无法使用系统中的真实知识库
- 严重影响 RAG 功能使用

**影响等级：** 🔴 严重 - 核心功能不可用

---

### 问题 2：缺少 Embedding 模型选择

**当前状态：** RAG 配置界面无 Embedding 模型选择

**问题：**
- RAG 检索依赖 Embedding 模型进行向量化
- 用户无法选择不同的模型
- 无法适配不同的向量维度需求

**影响等级：** 🟡 中等 - 功能不够完善

---

### 问题 3：输出变量定义不友好

**当前状态：** 用户需要手动输入提取路径

**问题：**
- 用户需要记住 `documents`, `context` 等路径
- 容易输入错误
- 缺少提示和辅助

**影响等级：** 🟡 中等 - 用户体验不佳

---

## 改进设计

### 设计目标

1. **功能完整性** - 支持真实知识库选择
2. **配置灵活性** - 支持多种 Embedding 模型
3. **用户体验** - 提供预设选项，降低使用难度
4. **一致性** - 与 LLM 节点改进模式保持一致

---

### 改进 1：知识库选择

#### 数据源设计

**API：** `useKnowledgeStore().knowledgeBases`

**数据结构：**
```typescript
interface KnowledgeBase {
  id: string
  name: string
  description?: string
  document_count?: number
  embedding_model?: string
  enabled?: boolean
  // ... 其他字段
}
```

#### UI 设计

**组件：** `el-select` (multiple, filterable)

**显示内容：**
- 主文本：知识库名称
- 副文本：文档数量（灰色小字）
- 过滤：支持搜索知识库名称

**交互逻辑：**
```vue
<el-select
  v-model="form.config.kbIds"
  multiple
  placeholder="选择知识库"
  filterable
>
  <el-option
    v-for="kb in enabledKnowledgeBases"
    :key="kb.id"
    :label="kb.name"
    :value="kb.id"
  >
    <div style="display: flex; justify-content: space-between;">
      <span>{{ kb.name }}</span>
      <span style="color: #909399; font-size: 12px;">
        {{ kb.document_count || 0 }} 篇文档
      </span>
    </div>
  </el-option>
</el-select>
```

**错误处理：**
- 如果没有知识库，显示提示："暂无可用知识库，请先在知识库管理中创建"
- 使用 `v-if` 条件渲染提示信息

---

### 改进 2：Embedding 模型选择

#### 数据源设计

**API：** `useSettingsStore().models.embed`

**数据结构：**
```typescript
interface ModelDef {
  name: string
  prov: string
  dim?: string | number
  def?: boolean
  enabled?: boolean
  // ... 其他字段
}
```

#### UI 设计

**组件：** `el-select` (filterable, clearable)

**显示内容：**
- 主文本：模型名称
- 标签：默认模型标识（绿色 tag）
- 过滤：支持搜索模型名称

**交互逻辑：**
```vue
<el-form-item label="向量模型">
  <el-select
    v-model="form.config.embedModel"
    placeholder="选择 Embedding 模型"
    filterable
    clearable
  >
    <el-option
      v-for="model in enabledEmbedModels"
      :key="model.name"
      :label="model.name + (model.def ? ' (默认)' : '')"
      :value="model.name"
    >
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span>{{ model.name }}</span>
        <el-tag v-if="model.def" type="success" size="small">默认</el-tag>
      </div>
    </el-option>
  </el-select>
</el-form-item>
```

**默认行为：**
- 字段为可选（clearable）
- 如果用户未选择，后端使用系统默认模型
- 前端显示默认模型标识

**错误处理：**
- 如果没有可用模型，显示提示："暂无可用模型，请先在系统设置中配置"

---

### 改进 3：输出变量定义

#### 预设选项设计

**预设列表：**
```typescript
const ragOutputPresets = [
  { label: '文档列表', value: 'documents', desc: '检索到的文档列表' },
  { label: '上下文', value: 'context', desc: '拼接后的上下文文本' },
  { label: '相似度分数', value: 'scores', desc: '每个文档的相似度分数' },
  { label: '查询文本', value: 'query', desc: '用户的查询文本' },
  { label: '文档数量', value: 'count', desc: '检索到的文档数量' }
]
```

#### UI 设计

**快速选择按钮：**
```vue
<el-alert type="info" :closable="false" style="margin-bottom: 12px">
  <template #title>
    <strong>快速选择</strong>
  </template>
  <div style="margin-top: 8px;">
    <el-button
      v-for="preset in ragOutputPresets"
      :key="preset.value"
      size="small"
      style="margin-right: 8px; margin-bottom: 8px;"
      @click="addPresetOutput(preset.value, preset.label)"
    >
      {{ preset.label }}
    </el-button>
  </div>
</el-alert>
```

**下拉选择：**
```vue
<el-select
  v-model="item.source"
  placeholder="选择输出字段"
  filterable
  style="flex: 1"
  clearable
>
  <el-option
    v-for="preset in ragOutputPresets"
    :key="preset.value"
    :label="preset.label"
    :value="preset.value"
  >
    <div>
      <div>{{ preset.label }}</div>
      <div style="font-size: 12px; color: #909399;">{{ preset.desc }}</div>
    </div>
  </el-option>
</el-select>
```

#### 交互流程

1. **快速添加：**
   - 用户点击"文档列表"按钮
   - 自动添加 `{ name: 'documents', source: 'documents' }`

2. **手动添加：**
   - 用户点击"+ 添加输出变量"
   - 从下拉框选择输出字段
   - 下拉选项显示字段名称和详细描述

3. **编辑：**
   - 用户可以修改变量名
   - 可以通过下拉框重新选择输出字段
   - 可以删除不需要的变量

---

## 技术实现

### 文件修改清单

**主文件：** `frontend/src/views/workflow/components/NodeConfigModal.vue`

**修改内容：**

#### 1. 引入依赖

**位置：** `<script setup>` 顶部

**添加内容：**
```typescript
import { useKnowledgeStore } from '@/stores/knowledge'
import { useSettingsStore } from '@/stores/settings'

const knowledgeStore = useKnowledgeStore()
const settingsStore = useSettingsStore()
```

**修改位置：** `onMounted` 钩子

**添加内容：**
```typescript
onMounted(() => {
  if (toolStore.tools.length === 0) {
    toolStore.loadTools()
  }
  // 新增：加载知识库和模型配置
  if (knowledgeStore.knowledgeBases.length === 0) {
    knowledgeStore.loadKnowledgeBases()
  }
  if (settingsStore.models.embed.length === 0) {
    settingsStore.loadModels()
  }
})
```

---

#### 2. 添加计算属性

**位置：** `computed` 属性区域

**添加内容：**
```typescript
// ===== RAG 节点：从系统获取知识库和模型 =====
const enabledKnowledgeBases = computed(() => {
  return knowledgeStore.knowledgeBases.filter(kb => kb.enabled !== false)
})

const enabledEmbedModels = computed(() => {
  return settingsStore.models.embed.filter(m => m.enabled !== false)
})

// RAG 输出变量预设选项
const ragOutputPresets = [
  { label: '文档列表', value: 'documents', desc: '检索到的文档列表' },
  { label: '上下文', value: 'context', desc: '拼接后的上下文文本' },
  { label: '相似度分数', value: 'scores', desc: '每个文档的相似度分数' },
  { label: '查询文本', value: 'query', desc: '用户的查询文本' },
  { label: '文档数量', value: 'count', desc: '检索到的文档数量' }
]

// 判断是否为 RAG 节点输出变量配置
const isRAGOutputDef = computed(() => props.node?.type === 'rag' && showOutputDef.value)
```

---

#### 3. 修改 RAG 配置 UI

**位置：** `<template v-if="showRagConfig">`

**完整替换：**
```vue
<template v-if="showRagConfig">
  <el-divider content-position="left">RAG 配置</el-divider>

  <!-- 知识库选择 -->
  <el-form-item label="知识库">
    <el-select
      v-model="form.config.kbIds"
      multiple
      placeholder="选择知识库"
      filterable
      style="width: 100%"
    >
      <el-option
        v-for="kb in enabledKnowledgeBases"
        :key="kb.id"
        :label="kb.name"
        :value="kb.id"
      >
        <div style="display: flex; justify-content: space-between;">
          <span>{{ kb.name }}</span>
          <span style="color: #909399; font-size: 12px;">
            {{ kb.document_count || 0 }} 篇文档
          </span>
        </div>
      </el-option>
    </el-select>
    <div v-if="enabledKnowledgeBases.length === 0" style="color: #909399; font-size: 12px; margin-top: 4px;">
      暂无可用知识库，请先在知识库管理中创建
    </div>
  </el-form-item>

  <!-- Embedding 模型选择 -->
  <el-form-item label="向量模型">
    <el-select
      v-model="form.config.embedModel"
      placeholder="选择 Embedding 模型"
      filterable
      clearable
      style="width: 100%"
    >
      <el-option
        v-for="model in enabledEmbedModels"
        :key="model.name"
        :label="model.name + (model.def ? ' (默认)' : '')"
        :value="model.name"
      >
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>{{ model.name }}</span>
          <el-tag v-if="model.def" type="success" size="small">默认</el-tag>
        </div>
      </el-option>
    </el-select>
    <div v-if="enabledEmbedModels.length === 0" style="color: #909399; font-size: 12px; margin-top: 4px;">
      暂无可用模型，请先在系统设置中配置
    </div>
  </el-form-item>

  <!-- Top K -->
  <el-form-item label="Top K">
    <el-input-number v-model="form.config.topK" :min="1" :max="20" />
  </el-form-item>

  <!-- 相似度阈值 -->
  <el-form-item label="相似度阈值">
    <el-slider v-model="form.config.threshold" :min="0" :max="1" :step="0.1" />
  </el-form-item>
</template>
```

---

#### 4. 修改输出变量定义 UI

**位置：** `<template v-if="showOutputDef">`

**在现有代码前添加：**
```vue
<!-- ===== 输出变量定义 ===== -->
<template v-if="showOutputDef">
  <el-divider content-position="left">输出变量定义</el-divider>

  <!-- RAG 节点：预设输出选项 -->
  <template v-if="isRAGOutputDef">
    <el-alert type="info" :closable="false" style="margin-bottom: 12px">
      <template #title>
        <strong>快速选择</strong>
      </template>
      <div style="margin-top: 8px;">
        <el-button
          v-for="preset in ragOutputPresets"
          :key="preset.value"
          size="small"
          style="margin-right: 8px; margin-bottom: 8px;"
          @click="addPresetOutput(preset.value, preset.label)"
        >
          {{ preset.label }}
        </el-button>
      </div>
    </el-alert>

    <div v-for="(item, idx) in form.outputVariables" :key="'ov-' + idx" class="param-row">
      <el-input v-model="item.name" placeholder="变量名" style="width: 140px" />
      <el-select v-model="item.source" placeholder="选择输出字段" filterable style="flex: 1" clearable>
        <el-option
          v-for="preset in ragOutputPresets"
          :key="preset.value"
          :label="preset.label"
          :value="preset.value"
        >
          <div>
            <div>{{ preset.label }}</div>
            <div style="font-size: 12px; color: #909399;">{{ preset.desc }}</div>
          </div>
        </el-option>
      </el-select>
      <el-button type="danger" link @click="removeOutputVar(idx)">删除</el-button>
    </div>
  </template>

  <!-- LLM 节点：预设输出选项 -->
  <template v-else-if="isLLMOutputDef">
    <!-- 现有 LLM 输出配置代码 -->
  </template>

  <!-- 其他节点：通用输出定义 -->
  <template v-else>
    <!-- 现有通用输出配置代码 -->
  </template>

  <el-button plain style="width: 100%; margin-top: 8px" @click="addOutputVar">
    + 添加输出变量
  </el-button>
</template>
```

---

#### 5. 更新预览行

**位置：** `buildPreviewRows()` 函数

**修改 RAG 节点部分：**
```typescript
if (props.node?.type === 'rag') {
  // 显示选中的知识库
  const selectedKBs = enabledKnowledgeBases.value
    .filter(kb => form.value.config.kbIds?.includes(kb.id))
    .map(kb => kb.name)
    .join(', ')
  rows.push(['知识库', selectedKBs || '未选择'])

  // 显示选中的 Embedding 模型
  if (form.value.config.embedModel) {
    rows.push(['向量模型', form.value.config.embedModel])
  }

  // 显示检索参数
  rows.push(['Top K', String(form.value.config.topK || 5)])
  rows.push(['阈值', String(form.value.config.threshold || 0.5)])
}
```

---

## 测试计划

### 功能测试

#### 测试 1：知识库选择

**前置条件：**
- 系统中已创建至少 1 个知识库
- 知识库包含文档

**测试步骤：**
1. 打开工作流编辑器
2. 拖拽 RAG 检索节点到画布
3. 双击节点打开配置面板
4. 点击知识库下拉框

**预期结果：**
- ✅ 显示系统中所有启用的知识库
- ✅ 每个知识库显示名称和文档数量
- ✅ 支持搜索过滤知识库
- ✅ 可以选择多个知识库

**错误场景：**
- 如果没有知识库，显示提示信息

---

#### 测试 2：Embedding 模型选择

**前置条件：**
- 系统设置中已配置至少 1 个 Embedding 模型

**测试步骤：**
1. 打开 RAG 节点配置面板
2. 点击向量模型下拉框

**预期结果：**
- ✅ 显示系统中所有启用的 Embedding 模型
- ✅ 默认模型显示绿色标签
- ✅ 支持搜索过滤模型
- ✅ 可以为空（使用系统默认）

**错误场景：**
- 如果没有可用模型，显示提示信息

---

#### 测试 3：输出变量配置

**测试步骤：**
1. 打开 RAG 节点配置面板
2. 滚动到输出变量定义部分
3. 点击"文档列表"按钮
4. 点击"上下文"按钮

**预期结果：**
- ✅ 显示"快速选择"提示框
- ✅ 点击按钮自动添加对应的输出变量
- ✅ 输出变量包含正确的变量名和提取路径
- ✅ 下拉选择显示字段名称和描述

---

### 集成测试

#### 测试 4：完整流程

**测试步骤：**
1. 创建新工作流
2. 添加开始节点（定义输入参数）
3. 添加 RAG 检索节点
4. 配置知识库、模型、输出变量
5. 添加其他节点引用 RAG 输出
6. 保存工作流

**预期结果：**
- ✅ 配置正确保存到数据库
- ✅ 重新打开后配置保持不变
- ✅ 节点预览显示正确信息

---

### 兼容性测试

#### 测试 5：与现有节点兼容

**测试范围：**
- LLM 节点配置
- 工具节点配置
- 其他节点配置

**预期结果：**
- ✅ 其他节点配置不受影响
- ✅ 输出变量引用正常工作
- ✅ 整体用户体验一致

---

## 风险评估

### 技术风险

#### 风险 1：知识库 Store 未加载

**场景：** 知识库 Store 数据未初始化

**影响：** 下拉列表为空

**缓解措施：**
- 在 `onMounted` 中检查并加载
- 显示友好的提示信息
- 提供跳转链接到知识库管理

**风险等级：** 🟡 中等

---

#### 风险 2：模型配置未加载

**场景：** 系统设置 Store 数据未初始化

**影响：** Embedding 模型列表为空

**缓解措施：**
- 在 `onMounted` 中检查并加载
- 显示友好的提示信息
- 提供跳转链接到系统设置

**风险等级：** 🟡 中等

---

### 业务风险

#### 风险 3：用户未创建知识库

**场景：** 新用户第一次使用，还没有创建知识库

**影响：** 无法使用 RAG 功能

**缓解措施：**
- 显示清晰的引导提示
- 提供"创建知识库"按钮或链接
- 在文档中说明前置条件

**风险等级：** 🟢 低

---

## 回归计划

### 回滚策略

如果发现严重问题，可以：

1. **立即回滚：**
   - 恢复 `NodeConfigModal.vue` 到修改前版本
   - 重新部署前端

2. **部分禁用：**
   - 保留知识库选择改进
   - 禁用 Embedding 模型选择（使用默认）
   - 禁用输出变量预设（恢复手动输入）

---

### 监控指标

**监控内容：**
- RAG 节点配置成功率
- 用户反馈和错误报告
- 工作流保存/加载成功率

**监控周期：** 改进后 1 周

---

## 后续改进

### 短期（1-2 周）

1. **模板渲染节点改进**
   - 添加模板库管理
   - 添加模板验证功能
   - 输出变量预设

2. **人工介入节点改进**
   - 添加审批表单配置
   - 添加超时设置
   - 添加通知配置

---

### 中期（1-2 月）

1. **代码执行节点改进**
   - 添加代码模板库
   - 添加代码验证功能
   - 添加依赖管理

2. **HTTP 请求节点改进**
   - 添加认证配置
   - 添加请求模板库
   - 输出变量预设

---

### 长期（3-6 月）

1. **条件分支节点改进**
   - 添加表达式语法说明
   - 添加变量选择器
   - 添加表达式验证

2. **变量赋值节点改进**
   - 支持批量赋值
   - 支持变量类型验证
   - 支持表达式计算

---

## 参考文档

- [工作流节点输出设置分析报告](../superpowers/specs/2026-09-16-workflow-node-output-settings-analysis.md)
- [LLM 节点改进设计](../superpowers/specs/2026-09-16-llm-node-improvements.md)（如果存在）
- [EasyRAG 前端开发指南](../../frontend/README.md)
- [Vue 3 文档](https://vuejs.org/)
- [Element Plus 文档](https://element-plus.org/)

---

## 附录：代码差异预览

### 知识库选择改进

**改进前：**
```vue
<el-select v-model="form.config.kbIds" multiple placeholder="选择知识库">
  <el-option label="知识库 A" value="kb-1" />
  <el-option label="知识库 B" value="kb-2" />
</el-select>
```

**改进后：**
```vue
<el-select v-model="form.config.kbIds" multiple placeholder="选择知识库" filterable>
  <el-option
    v-for="kb in enabledKnowledgeBases"
    :key="kb.id"
    :label="kb.name"
    :value="kb.id"
  >
    <div style="display: flex; justify-content: space-between;">
      <span>{{ kb.name }}</span>
      <span style="color: #909399; font-size: 12px;">
        {{ kb.document_count || 0 }} 篇文档
      </span>
    </div>
  </el-option>
</el-select>
```

---

### Embedding 模型选择

**改进前：** 无此配置项

**改进后：** 新增完整配置项（见上文）

---

### 输出变量定义

**改进前：** 手动输入提取路径

**改进后：** 预设选项 + 下拉选择（见上文）

---

**文档版本：** 1.0
**最后更新：** 2026-09-16
**作者：** Claude Code Assistant
<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { WfNode } from '@/types/workflow'

const props = defineProps<{
  visible: boolean
  node: WfNode | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'save', node: WfNode): void
}>()

const form = ref({
  name: '',
  config: {} as Record<string, any>
})

watch(
  () => props.node,
  (node) => {
    if (node) {
      form.value.name = node.name
      form.value.config = node.data?.config || {}
    }
  },
  { immediate: true }
)

const nodeTypeLabel = computed(() => {
  const labels: Record<string, string> = {
    start: '开始节点',
    end: '结束节点',
    condition: '条件分支',
    loop: '循环',
    human: '人工介入',
    variable_assign: '变量赋值',
    template_render: '模板渲染',
    llm: 'LLM 生成',
    rag: 'RAG 检索',
    code: '代码执行',
    http: 'HTTP 请求',
    tool: '外部工具'
  }
  return labels[props.node?.type || ''] || '节点配置'
})

const showModelSelect = computed(() => props.node?.type === 'llm')
const showRagConfig = computed(() => props.node?.type === 'rag')
const showConditionConfig = computed(() => props.node?.type === 'condition')
const showVariableConfig = computed(() => props.node?.type === 'variable_assign')
const showTemplateConfig = computed(() => props.node?.type === 'template_render')
const showCodeConfig = computed(() => props.node?.type === 'code')
const showHttpConfig = computed(() => props.node?.type === 'http')
const showToolConfig = computed(() => props.node?.type === 'tool')

function handleClose() {
  emit('update:visible', false)
}

function handleSave() {
  if (!props.node) return
  
  const updatedNode: WfNode = {
    ...props.node,
    name: form.value.name,
    data: {
      ...props.node.data,
      config: form.value.config,
      rows: buildPreviewRows()
    }
  }
  
  emit('save', updatedNode)
  emit('update:visible', false)
}

function buildPreviewRows(): [string, string][] {
  const rows: [string, string][] = []
  
  if (props.node?.type === 'llm') {
    rows.push(['模型', form.value.config.model || 'gpt-4'])
    rows.push(['温度', String(form.value.config.temperature || 0.7)])
  } else if (props.node?.type === 'rag') {
    rows.push(['Top K', String(form.value.config.topK || 5)])
    rows.push(['阈值', String(form.value.config.threshold || 0.5)])
  } else if (props.node?.type === 'condition') {
    rows.push(['条件', form.value.config.expression || ''])
  } else if (props.node?.type === 'http') {
    rows.push(['方法', form.value.config.method || 'GET'])
    rows.push(['URL', form.value.config.url || ''])
  } else if (props.node?.type === 'code') {
    rows.push(['语言', form.value.config.language || 'python'])
  }
  
  return rows
}

function handleDialogUpdate(val: boolean) {
  emit('update:visible', val)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="nodeTypeLabel"
    width="600px"
    @update:model-value="handleDialogUpdate"
    @close="handleClose"
  >
    <el-form :model="form" label-width="100px">
      <el-form-item label="节点名称">
        <el-input v-model="form.name" placeholder="请输入节点名称" />
      </el-form-item>
      
      <template v-if="showModelSelect">
        <el-divider content-position="left">LLM 配置</el-divider>
        <el-form-item label="模型">
          <el-select v-model="form.config.model" placeholder="选择模型">
            <el-option label="GPT-4" value="gpt-4" />
            <el-option label="GPT-3.5 Turbo" value="gpt-3.5-turbo" />
            <el-option label="Claude 3" value="claude-3" />
            <el-option label="Qwen-Max" value="qwen-max" />
          </el-select>
        </el-form-item>
        <el-form-item label="系统提示">
          <el-input v-model="form.config.systemPrompt" type="textarea" :rows="3" placeholder="系统提示词" />
        </el-form-item>
        <el-form-item label="温度">
          <el-slider v-model="form.config.temperature" :min="0" :max="1" :step="0.1" />
        </el-form-item>
        <el-form-item label="最大 Token">
          <el-input-number v-model="form.config.maxTokens" :min="100" :max="4000" :step="100" />
        </el-form-item>
      </template>
      
      <template v-if="showRagConfig">
        <el-divider content-position="left">RAG 配置</el-divider>
        <el-form-item label="知识库">
          <el-select v-model="form.config.kbIds" multiple placeholder="选择知识库">
            <el-option label="知识库 A" value="kb-1" />
            <el-option label="知识库 B" value="kb-2" />
          </el-select>
        </el-form-item>
        <el-form-item label="Top K">
          <el-input-number v-model="form.config.topK" :min="1" :max="20" />
        </el-form-item>
        <el-form-item label="相似度阈值">
          <el-slider v-model="form.config.threshold" :min="0" :max="1" :step="0.1" />
        </el-form-item>
      </template>
      
      <template v-if="showConditionConfig">
        <el-divider content-position="left">条件配置</el-divider>
        <el-form-item label="条件表达式">
          <el-input v-model="form.config.expression" placeholder="例: score > 0.8" />
        </el-form-item>
        <el-form-item label="是 分支标签">
          <el-input v-model="form.config.trueLabel" placeholder="默认: 是" />
        </el-form-item>
        <el-form-item label="否 分支标签">
          <el-input v-model="form.config.falseLabel" placeholder="默认: 否" />
        </el-form-item>
      </template>
      
      <template v-if="showVariableConfig">
        <el-divider content-position="left">变量配置</el-divider>
        <el-form-item label="变量名">
          <el-input v-model="form.config.varName" placeholder="变量名" />
        </el-form-item>
        <el-form-item label="变量值">
          <el-input v-model="form.config.varValue" placeholder="变量值" />
        </el-form-item>
      </template>
      
      <template v-if="showTemplateConfig">
        <el-divider content-position="left">模板配置</el-divider>
        <el-form-item label="模板内容">
          <el-input v-model="form.config.template" type="textarea" :rows="5" placeholder="Jinja2 模板" />
        </el-form-item>
      </template>
      
      <template v-if="showCodeConfig">
        <el-divider content-position="left">代码配置</el-divider>
        <el-form-item label="语言">
          <el-select v-model="form.config.language">
            <el-option label="Python" value="python" />
            <el-option label="JavaScript" value="javascript" />
            <el-option label="Shell" value="shell" />
          </el-select>
        </el-form-item>
        <el-form-item label="代码">
          <el-input v-model="form.config.code" type="textarea" :rows="8" placeholder="输入代码..." />
        </el-form-item>
      </template>
      
      <template v-if="showHttpConfig">
        <el-divider content-position="left">HTTP 配置</el-divider>
        <el-form-item label="方法">
          <el-select v-model="form.config.method" style="width: 100px">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="DELETE" value="DELETE" />
          </el-select>
        </el-form-item>
        <el-form-item label="URL">
          <el-input v-model="form.config.url" placeholder="https://api.example.com" />
        </el-form-item>
        <el-form-item label="请求头">
          <el-input v-model="form.config.headers" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="请求体">
          <el-input v-model="form.config.body" type="textarea" :rows="3" />
        </el-form-item>
      </template>
      
      <template v-if="showToolConfig">
        <el-divider content-position="left">工具配置</el-divider>
        <el-form-item label="工具 ID">
          <el-input v-model="form.config.toolId" placeholder="工具唯一标识" />
        </el-form-item>
        <el-form-item label="参数">
          <el-input v-model="form.config.params" type="textarea" :rows="3" />
        </el-form-item>
      </template>
    </el-form>
    
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

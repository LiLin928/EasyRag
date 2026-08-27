<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import type { WfNode, OutputParamOption } from '@/types/workflow'
import { useWorkflowEditorStore } from '@/stores/workflow'
import { getUpstreamOutputOptions, getAllNodesOutputOptions } from '@/composables/useWorkflowParams'
import { useToolStore } from '@/stores/tool'
import type { ToolParam } from '@/types/tool'

const props = defineProps<{
  visible: boolean
  node: WfNode | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'save', node: WfNode): void
}>()

const editorStore = useWorkflowEditorStore()
const toolStore = useToolStore()

onMounted(() => {
  if (toolStore.tools.length === 0) {
    toolStore.loadTools()
  }
})

const form = ref({
  name: '',
  config: {} as Record<string, any>,
  inputVariables: [] as Array<{ name: string; source?: string; default?: any }>,
  outputVariables: [] as Array<{ name: string; source?: string }>
})

watch(
  () => props.node,
  (node) => {
    if (node) {
      form.value.name = node.name
      const cfg = node.data?.config || {}
      form.value.config = { ...cfg }
      form.value.inputVariables = (cfg.input_variables ? [...cfg.input_variables] : [])
        .map((v: any) => ({ ...v }))
      form.value.outputVariables = (cfg.output_variables ? [...cfg.output_variables] : [])
        .map((v: any) => ({ ...v }))
    }
  },
  { immediate: true }
)

const nodeTypeLabel = computed(() => {
  const labels: Record<string, string> = {
    start: '开始节点',
    end: '结束节点',
    condition: '条件分支',
    loop: '循环开始',
    loop_end: '循环结束',
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
const showLoopConfig = computed(() => props.node?.type === 'loop')
const showLoopEndConfig = computed(() => props.node?.type === 'loop_end')

// ===== 工具节点：从系统工具库选择 =====
const enabledTools = computed(() => toolStore.tools.filter(t => t.enabled))
const selectedTool = computed(() => toolStore.tools.find(t => t.id === form.value.config.toolId) || null)
const selectedToolParams = computed<ToolParam[]>(() => selectedTool.value?.params || [])

// 确保 params 是对象
const toolParamValues = computed({
  get: () => {
    if (typeof form.value.config.params === 'string') {
      try { return JSON.parse(form.value.config.params || '{}') } catch { return {} }
    }
    return form.value.config.params || {}
  },
  set: (val: Record<string, any>) => { form.value.config.params = val }
})

function onToolChange(toolId: string) {
  form.value.config.toolId = toolId
  // 重置参数为默认值
  const tool = toolStore.tools.find(t => t.id === toolId)
  if (tool?.params?.length) {
    const defaults: Record<string, any> = {}
    for (const p of tool.params) {
      if (p.d) defaults[p.n] = p.d
    }
    form.value.config.params = defaults
  } else {
    form.value.config.params = {}
  }
}

// ===== 参数传递 =====

// 开始节点：定义工作流输入参数
const isStartNode = computed(() => props.node?.type === 'start')
// 结束节点：定义工作流输出映射
const isEndNode = computed(() => props.node?.type === 'end')
// 其他节点：输入变量映射 + 输出变量定义
const showInputMapping = computed(() => !isStartNode.value && !isEndNode.value)
const showOutputDef = computed(() => {
  const t = props.node?.type
  return t === 'llm' || t === 'rag' || t === 'code' || t === 'http' || t === 'tool' || t === 'template_render'
})

// 上游可引用变量选项（用于输入变量 source 下拉）
const upstreamOptions = computed<OutputParamOption[]>(() => {
  if (!props.node) return []
  return getUpstreamOutputOptions(props.node.id, editorStore.nodes, editorStore.edges)
})

// 所有节点输出选项（用于结束节点输出映射）
const allOutputOptions = computed<OutputParamOption[]>(() => {
  if (!props.node) return []
  return getAllNodesOutputOptions(props.node.id, editorStore.nodes)
})

function addInputVar() {
  form.value.inputVariables.push({ name: '', source: '' })
}
function removeInputVar(index: number) {
  form.value.inputVariables.splice(index, 1)
}
function addOutputVar() {
  form.value.outputVariables.push({ name: '', source: '' })
}
function removeOutputVar(index: number) {
  form.value.outputVariables.splice(index, 1)
}
// 开始节点输入参数
function addStartInput() {
  form.value.inputVariables.push({ name: '', source: '' })
}
function removeStartInput(index: number) {
  form.value.inputVariables.splice(index, 1)
}
// 结束节点输出映射
function addEndOutput() {
  form.value.outputVariables.push({ name: '', source: '' })
}
function removeEndOutput(index: number) {
  form.value.outputVariables.splice(index, 1)
}

function handleClose() {
  emit('update:visible', false)
}

function handleSave() {
  if (!props.node) return

  const config = { ...form.value.config }
  // 写入输入/输出变量到 config
  if (isStartNode.value) {
    config.input_variables = form.value.inputVariables
  } else if (isEndNode.value) {
    config.output_variables = form.value.outputVariables
  } else {
    if (form.value.inputVariables.length) config.input_variables = form.value.inputVariables
    if (form.value.outputVariables.length) config.output_variables = form.value.outputVariables
  }

  const updatedNode: WfNode = {
    ...props.node,
    name: form.value.name,
    data: {
      ...props.node.data,
      config,
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
  } else if (props.node?.type === 'tool') {
    rows.push(['工具', selectedTool.value?.name || form.value.config.toolId || ''])
  } else if (props.node?.type === 'loop') {
    rows.push(['模式', form.value.config.loop_mode || 'foreach'])
  } else if (props.node?.type === 'loop_end') {
    rows.push(['收集', form.value.config.collect_mode || 'array'])
  }

  // 追加输入/输出变量计数
  if (form.value.inputVariables.length) {
    rows.push(['输入变量', String(form.value.inputVariables.length)])
  }
  if (form.value.outputVariables.length) {
    rows.push(['输出变量', String(form.value.outputVariables.length)])
  }

  return rows
}

function handleDialogUpdate(val: boolean) {
  emit('update:visible', val)
}
</script>

<template>
  <el-drawer
    :model-value="visible"
    :title="nodeTypeLabel"
    direction="rtl"
    size="640px"
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
        <el-form-item label="选择工具">
          <el-select
            v-model="form.config.toolId"
            placeholder="请选择系统工具"
            filterable
            style="width: 100%"
            @change="onToolChange"
          >
            <el-option
              v-for="t in enabledTools"
              :key="t.id"
              :label="t.name + ' (' + t.type + ')'"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selectedTool && selectedTool.desc" label="说明">
          <span style="color: #909399; font-size: 12px">{{ selectedTool.desc }}</span>
        </el-form-item>
        <template v-if="selectedToolParams.length">
          <el-divider content-position="left">工具参数</el-divider>
          <el-form-item
            v-for="param in selectedToolParams"
            :key="param.n"
            :label="param.n"
          >
            <el-switch
              v-if="param.t === 'boolean'"
              v-model="toolParamValues[param.n]"
            />
            <el-input-number
              v-else-if="param.t === 'number'"
              v-model="toolParamValues[param.n]"
              :placeholder="param.d || ''"
            />
            <el-input
              v-else-if="param.t === 'object' || param.t === 'array'"
              v-model="toolParamValues[param.n]"
              type="textarea"
              :rows="3"
              :placeholder="param.d || ''"
            />
            <el-input
              v-else
              v-model="toolParamValues[param.n]"
              :placeholder="param.d || ''"
            />
          </el-form-item>
        </template>
      </template>

      <!-- ===== 循环开始节点配置 ===== -->
      <template v-if="showLoopConfig">
        <el-divider content-position="left">循环配置</el-divider>
        <el-form-item label="循环模式">
          <el-select v-model="form.config.loop_mode" placeholder="选择循环模式">
            <el-option label="遍历数组 (foreach)" value="foreach" />
            <el-option label="指定次数 (count)" value="count" />
            <el-option label="条件循环 (while)" value="while" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.config.loop_mode === 'foreach'" label="遍历变量">
          <el-select
            v-model="form.config.loop_variable"
            placeholder="选择要遍历的数组变量"
            filterable
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="opt in upstreamOptions"
              :key="opt.path"
              :label="opt.name"
              :value="opt.path"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.config.loop_mode === 'count'" label="循环次数">
          <el-input-number v-model="form.config.max_iterations" :min="1" :max="10000" />
        </el-form-item>
        <el-form-item v-if="form.config.loop_mode === 'while'" label="循环条件">
          <el-input v-model="form.config.condition_expr" placeholder="例: index < 10" />
        </el-form-item>
        <el-form-item label="安全上限">
          <el-input-number v-model="form.config.max_iterations" :min="1" :max="100000" :step="100" />
          <span style="color: #909399; font-size: 12px; margin-left: 8px">防止死循环</span>
        </el-form-item>
        <el-alert type="info" :closable="false" style="margin-bottom: 12px">
          输出变量：item（当前元素）、index（当前索引）。连接到循环结束节点界定循环体边界。
        </el-alert>
      </template>

      <!-- ===== 循环结束节点配置 ===== -->
      <template v-if="showLoopEndConfig">
        <el-divider content-position="left">循环结束配置</el-divider>
        <el-form-item label="收集变量">
          <el-select
            v-model="form.config.collect_variable"
            placeholder="选择要收集的变量"
            filterable
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="opt in upstreamOptions"
              :key="opt.path"
              :label="opt.name"
              :value="opt.path"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="收集模式">
          <el-select v-model="form.config.collect_mode" placeholder="选择收集模式">
            <el-option label="聚合成数组 (array)" value="array" />
            <el-option label="取最后一轮 (last)" value="last" />
          </el-select>
        </el-form-item>
        <el-alert type="info" :closable="false" style="margin-bottom: 12px">
          循环开始与循环结束之间的节点构成循环体，每轮执行一次。循环结束后输出聚合的 result 变量。
        </el-alert>
      </template>

      <!-- ===== 开始节点：工作流输入参数 ===== -->
      <template v-if="isStartNode">
        <el-divider content-position="left">工作流输入参数</el-divider>
        <div v-for="(item, idx) in form.inputVariables" :key="'si-' + idx" class="param-row">
          <el-input v-model="item.name" placeholder="参数名" style="width: 140px" />
          <el-input v-model="item.source" placeholder="类型(如 string)" style="width: 120px" />
          <el-button type="danger" link @click="removeStartInput(idx)">删除</el-button>
        </div>
        <el-button plain style="width: 100%; margin-top: 8px" @click="addStartInput">+ 添加输入参数</el-button>
      </template>

      <!-- ===== 结束节点：工作流输出映射 ===== -->
      <template v-if="isEndNode">
        <el-divider content-position="left">工作流输出映射</el-divider>
        <el-alert v-if="allOutputOptions.length === 0" type="info" :closable="false" style="margin-bottom: 12px">
          请先添加其他节点以选择输出参数
        </el-alert>
        <div v-for="(item, idx) in form.outputVariables" :key="'eo-' + idx" class="param-row">
          <el-input v-model="item.name" placeholder="输出变量名" style="width: 140px" />
          <el-select v-model="item.source" placeholder="选择来源" filterable style="flex: 1" clearable>
            <el-option
              v-for="opt in allOutputOptions"
              :key="opt.path"
              :label="opt.name"
              :value="opt.path"
            />
          </el-select>
          <el-button type="danger" link @click="removeEndOutput(idx)">删除</el-button>
        </div>
        <el-button plain style="width: 100%; margin-top: 8px" @click="addEndOutput">+ 添加输出映射</el-button>
      </template>

      <!-- ===== 其他节点：输入变量映射 ===== -->
      <template v-if="showInputMapping">
        <el-divider content-position="left">输入变量映射</el-divider>
        <el-alert v-if="upstreamOptions.length === 0" type="info" :closable="false" style="margin-bottom: 12px">
          暂无上游节点输出可引用，请先连接上游节点
        </el-alert>
        <div v-for="(item, idx) in form.inputVariables" :key="'iv-' + idx" class="param-row">
          <el-input v-model="item.name" placeholder="参数名" style="width: 130px" />
          <el-select v-model="item.source" placeholder="选择上游变量" filterable style="flex: 1" clearable>
            <el-option
              v-for="opt in upstreamOptions"
              :key="opt.path"
              :label="opt.name"
              :value="opt.path"
            />
          </el-select>
          <el-button type="danger" link @click="removeInputVar(idx)">删除</el-button>
        </div>
        <el-button plain style="width: 100%; margin-top: 8px" @click="addInputVar">+ 添加输入变量</el-button>
      </template>

      <!-- ===== 输出变量定义 ===== -->
      <template v-if="showOutputDef">
        <el-divider content-position="left">输出变量定义</el-divider>
        <div v-for="(item, idx) in form.outputVariables" :key="'ov-' + idx" class="param-row">
          <el-input v-model="item.name" placeholder="变量名" style="width: 140px" />
          <el-input v-model="item.source" placeholder="提取路径(如 content)" style="flex: 1" />
          <el-button type="danger" link @click="removeOutputVar(idx)">删除</el-button>
        </div>
        <el-button plain style="width: 100%; margin-top: 8px" @click="addOutputVar">+ 添加输出变量</el-button>
      </template>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSave">保存</el-button>
    </template>
  </el-drawer>
</template>

<style lang="scss" scoped>
.param-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
</style>




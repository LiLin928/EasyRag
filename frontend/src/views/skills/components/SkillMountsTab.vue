<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import { useToolStore } from '@/stores/tool'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useWorkflowListStore } from '@/stores/workflow'

interface Props {
  tools: string[]
  docs: string[]
  wfs: string[]
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false
})

const emit = defineEmits<{
  update: [mounts: { tools: string[]; docs: string[]; wfs: string[] }]
}>()

const toolStore = useToolStore()
const knowledgeStore = useKnowledgeStore()
const workflowListStore = useWorkflowListStore()

const selectedTools = ref<string[]>([])
const selectedDocs = ref<string[]>([])
const selectedWfs = ref<string[]>([])

// 获取工具候选列表
const toolOptions = computed(() => {
  return toolStore.tools.map(t => ({
    label: t.name,
    value: t.id
  }))
})

// 获取文档候选列表
const docOptions = computed(() => {
  return knowledgeStore.docList.map(d => ({
    label: `${d.name} (${d.kbId})`,
    value: d.id
  }))
})

// 获取工作流候选列表
const workflowOptions = computed(() => {
  return workflowListStore.workflows.map(w => ({
    label: w.name,
    value: w.id
  }))
})

// 监听数据变化
watch(() => [props.tools, props.docs, props.wfs], ([tools, docs, wfs]) => {
  selectedTools.value = [...(tools || [])]
  selectedDocs.value = [...(docs || [])]
  selectedWfs.value = [...(wfs || [])]
}, { immediate: true })

// 监听选择变化
watch([selectedTools, selectedDocs, selectedWfs], ([tools, docs, wfs]) => {
  emit('update', {
    tools: tools || [],
    docs: docs || [],
    wfs: wfs || []
  })
}, { deep: true })

// 加载所需数据
onMounted(async () => {
  await toolStore.loadTools()
  await knowledgeStore.loadDocuments('kb1', 1, 100) // 加载所有文档
  await workflowListStore.loadWorkflows() // 加载工作流列表
})
</script>

<template>
  <div class="mounts-tab">
    <div class="mount-section">
      <div class="section-title">
        <el-icon><Tools /></el-icon>
        <span>挂载工具</span>
      </div>
      <el-select
        v-model="selectedTools"
        multiple
        placeholder="选择要挂载的工具"
        :disabled="readonly"
        style="width: 100%"
      >
        <el-option
          v-for="option in toolOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <div class="section-hint">已选择 {{ selectedTools.length }} 个工具</div>
    </div>

    <div class="mount-section">
      <div class="section-title">
        <el-icon><Document /></el-icon>
        <span>挂载文档</span>
      </div>
      <el-select
        v-model="selectedDocs"
        multiple
        placeholder="选择要挂载的知识库文档"
        :disabled="readonly"
        style="width: 100%"
      >
        <el-option
          v-for="option in docOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <div class="section-hint">已选择 {{ selectedDocs.length }} 个文档</div>
    </div>

    <div class="mount-section">
      <div class="section-title">
        <el-icon><Share /></el-icon>
        <span>挂载工作流</span>
      </div>
      <el-select
        v-model="selectedWfs"
        multiple
        placeholder="选择要挂载的工作流"
        :disabled="readonly"
        style="width: 100%"
      >
        <el-option
          v-for="option in workflowOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <div class="section-hint">已选择 {{ selectedWfs.length }} 个工作流</div>
    </div>

    <div class="mount-summary">
      <el-alert
        type="info"
        :closable="false"
        show-icon
      >
        <template #title>
          总计挂载：{{ selectedTools.length + selectedDocs.length + selectedWfs.length }} 个资源
        </template>
      </el-alert>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.mounts-tab {
  padding: 16px;
  height: 100%;
  overflow-y: auto;
}

.mount-section {
  margin-bottom: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-weight: 600;
  color: #303133;
}

.section-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

.mount-summary {
  padding-top: 16px;
  border-top: 1px solid #e0e0e0;
}
</style>

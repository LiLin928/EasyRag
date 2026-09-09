<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import { useToolStore } from '@/stores/tool'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useWorkflowListStore } from '@/stores/workflow'
import { useMcpStore } from '@/stores/mcp'
import { useSkillStore } from '@/stores/skill'

interface Props {
  tools: string[]
  docs: string[]
  wfs: string[]
  mcps: string[]
  skills: string[]
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false
})

const emit = defineEmits<{
  update: [capabilities: {
    tools: string[]
    docs: string[]
    wfs: string[]
    mcps: string[]
    skills: string[]
  }]
}>()

const toolStore = useToolStore()
const knowledgeStore = useKnowledgeStore()
const workflowListStore = useWorkflowListStore()
const mcpStore = useMcpStore()
const skillStore = useSkillStore()

const selectedTools = ref<string[]>([])
const selectedDocs = ref<string[]>([])
const selectedWfs = ref<string[]>([])
const selectedMcps = ref<string[]>([])
const selectedSkills = ref<string[]>([])

// 当前激活的 Tab
const activeTab = ref('tools')

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

// 获取 MCP 候选列表
const mcpOptions = computed(() => {
  return mcpStore.mcps.map(m => ({
    label: `${m.name} (${m.tp})`,
    value: m.id
  }))
})

// 获取技能候选列表
const skillOptions = computed(() => {
  return skillStore.skills.map(s => ({
    label: `${s.ico} ${s.name}`,
    value: s.id
  }))
})

// 监听数据变化
watch(() => [props.tools, props.docs, props.wfs, props.mcps, props.skills], ([tools, docs, wfs, mcps, skills]) => {
  selectedTools.value = [...(tools || [])]
  selectedDocs.value = [...(docs || [])]
  selectedWfs.value = [...(wfs || [])]
  selectedMcps.value = [...(mcps || [])]
  selectedSkills.value = [...(skills || [])]
}, { immediate: true })

// 监听选择变化
watch([selectedTools, selectedDocs, selectedWfs, selectedMcps, selectedSkills], ([tools, docs, wfs, mcps, skills]) => {
  emit('update', {
    tools: tools || [],
    docs: docs || [],
    wfs: wfs || [],
    mcps: mcps || [],
    skills: skills || []
  })
}, { deep: true })

// 加载所需数据
onMounted(async () => {
  await toolStore.loadTools()
  await knowledgeStore.loadDocuments('kb1', 1, 100) // 加载所有文档
  await workflowListStore.loadWorkflows()
  await mcpStore.loadMcps()
  await skillStore.loadSkills()
})

// 计算总挂载数
const totalCount = computed(() => {
  return selectedTools.value.length + selectedDocs.value.length +
         selectedWfs.value.length + selectedMcps.value.length +
         selectedSkills.value.length
})
</script>

<template>
  <div class="capability-picker">
    <el-tabs v-model="activeTab">
      <!-- 工具 Tab -->
      <el-tab-pane label="工具" name="tools">
        <div class="tab-content">
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
          <div class="selection-hint">已选择 {{ selectedTools.length }} 个工具</div>
        </div>
      </el-tab-pane>

      <!-- 文档 Tab -->
      <el-tab-pane label="文档" name="docs">
        <div class="tab-content">
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
          <div class="selection-hint">已选择 {{ selectedDocs.length }} 个文档</div>
        </div>
      </el-tab-pane>

      <!-- 工作流 Tab -->
      <el-tab-pane label="工作流" name="wfs">
        <div class="tab-content">
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
          <div class="selection-hint">已选择 {{ selectedWfs.length }} 个工作流</div>
        </div>
      </el-tab-pane>

      <!-- MCP Tab -->
      <el-tab-pane label="MCP" name="mcps">
        <div class="tab-content">
          <el-select
            v-model="selectedMcps"
            multiple
            placeholder="选择要挂载的 MCP 服务"
            :disabled="readonly"
            style="width: 100%"
          >
            <el-option
              v-for="option in mcpOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <div class="selection-hint">已选择 {{ selectedMcps.length }} 个 MCP 服务</div>
        </div>
      </el-tab-pane>

      <!-- 技能 Tab -->
      <el-tab-pane label="技能" name="skills">
        <div class="tab-content">
          <el-select
            v-model="selectedSkills"
            multiple
            placeholder="选择要挂载的技能"
            :disabled="readonly"
            style="width: 100%"
          >
            <el-option
              v-for="option in skillOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <div class="selection-hint">已选择 {{ selectedSkills.length }} 个技能</div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <div class="summary">
      <el-alert
        type="info"
        :closable="false"
        show-icon
      >
        <template #title>
          总计挂载：{{ totalCount }} 个资源
        </template>
      </el-alert>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.capability-picker {
  padding: 16px;
  background: #f9fafb;
  border-radius: 4px;
}

.tab-content {
  padding: 16px 0;
}

.selection-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

.summary {
  margin-top: 16px;
}
</style>
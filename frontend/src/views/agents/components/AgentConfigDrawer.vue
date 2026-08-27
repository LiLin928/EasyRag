<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useToolStore } from '@/stores/tool'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useWorkflowListStore } from '@/stores/workflow'
import { useMcpStore } from '@/stores/mcp'
import { useSkillStore } from '@/stores/skill'
import AgentCapabilityPicker from './AgentCapabilityPicker.vue'
import type { Agent } from '@/types/agent'

interface Props {
  visible: boolean
  data?: Agent | null
}

const props = withDefaults(defineProps<Props>(), {
  data: null
})

const emit = defineEmits<{
  'update:visible': [visible: boolean]
  submit: [data: Partial<Agent>]
}>()

const toolStore = useToolStore()
const knowledgeStore = useKnowledgeStore()
const workflowListStore = useWorkflowListStore()
const mcpStore = useMcpStore()
const skillStore = useSkillStore()

const formData = ref({
  name: '',
  desc: '',
  model: 'gpt-4o',
  prompt: '',
  temp: 0.7,
  maxtok: '2048',
  tools: [] as string[],
  docs: [] as string[],
  wfs: [] as string[],
  mcps: [] as string[],
  skills: [] as string[],
  enabled: true
})

const modelOptions = [
  { label: 'GPT-4o', value: 'gpt-4o' },
  { label: 'GPT-4o-mini', value: 'gpt-4o-mini' },
  { label: 'GPT-4-turbo', value: 'gpt-4-turbo' },
  { label: 'GPT-3.5-turbo', value: 'gpt-3.5-turbo' }
]

watch(() => props.visible, (visible) => {
  if (visible) {
    loadCandidateData()
    if (props.data) {
      formData.value = {
        name: props.data.name,
        desc: props.data.desc,
        model: props.data.model,
        prompt: props.data.prompt,
        temp: props.data.temp,
        maxtok: props.data.maxtok,
        tools: [...props.data.tools],
        docs: [...props.data.docs],
        wfs: [...props.data.wfs],
        mcps: [...props.data.mcps],
        skills: [...props.data.skills],
        enabled: props.data.enabled
      }
    } else {
      resetForm()
    }
  }
})

async function loadCandidateData() {
  await toolStore.loadTools()
  await knowledgeStore.loadDocuments('kb1', 1, 100)
  await workflowListStore.loadWorkflows()
  await mcpStore.loadMcps()
  await skillStore.loadSkills()
}

function resetForm() {
  formData.value = {
    name: '',
    desc: '',
    model: 'gpt-4o',
    prompt: '',
    temp: 0.7,
    maxtok: '2048',
    tools: [],
    docs: [],
    wfs: [],
    mcps: [],
    skills: [],
    enabled: true
  }
}

function handleCapabilityUpdate(capabilities: {
  tools: string[]
  docs: string[]
  wfs: string[]
  mcps: string[]
  skills: string[]
}) {
  formData.value.tools = capabilities.tools
  formData.value.docs = capabilities.docs
  formData.value.wfs = capabilities.wfs
  formData.value.mcps = capabilities.mcps
  formData.value.skills = capabilities.skills
}

function handleSubmit() {
  if (!formData.value.name.trim()) {
    ElMessage.warning('请输入智能体名称')
    return
  }
  emit('submit', formData.value)
}

function handleClose() {
  emit('update:visible', false)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="data ? '编辑智能体' : '新建智能体'"
    width="700px"
    :close-on-click-modal="false"
    @update:model-value="handleClose"
  >
    <div class="config-dialog">
      <el-form label-width="100px">
        <div class="form-section">
          <h4 class="section-title">基础信息</h4>
          <el-form-item label="名称" required>
            <el-input
              v-model="formData.name"
              placeholder="请输入智能体名称"
              maxlength="50"
              show-word-limit
            />
          </el-form-item>
          <el-form-item label="描述">
            <el-input
              v-model="formData.desc"
              type="textarea"
              :rows="2"
              placeholder="请输入智能体描述"
              maxlength="200"
              show-word-limit
            />
          </el-form-item>
        </div>

        <div class="form-section">
          <h4 class="section-title">模型配置</h4>
          <el-form-item label="模型">
            <el-select v-model="formData.model" style="width: 100%">
              <el-option
                v-for="option in modelOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="温度">
            <el-slider
              v-model="formData.temp"
              :min="0"
              :max="2"
              :step="0.1"
              :marks="{ 0: '0', 0.7: '0.7', 1: '1', 2: '2' }"
              show-input
            />
          </el-form-item>
          <el-form-item label="最大Token">
            <el-input
              v-model="formData.maxtok"
              placeholder="默认: 2048"
              type="number"
            />
          </el-form-item>
        </div>

        <div class="form-section">
          <h4 class="section-title">系统提示词</h4>
          <el-form-item label="Prompt">
            <el-input
              v-model="formData.prompt"
              type="textarea"
              :rows="8"
              placeholder="请输入系统提示词，定义智能体的角色和职责..."
            />
          </el-form-item>
        </div>

        <div class="form-section">
          <h4 class="section-title">能力挂载</h4>
          <AgentCapabilityPicker
            :tools="formData.tools"
            :docs="formData.docs"
            :wfs="formData.wfs"
            :mcps="formData.mcps"
            :skills="formData.skills"
            @update="handleCapabilityUpdate"
          />
        </div>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSubmit">
        {{ data ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.config-dialog {
  max-height: 65vh;
  overflow-y: auto;
  padding-right: 8px;
}

.form-section {
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid #f0f0f0;

  &:last-of-type {
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
  }
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 16px;
}
</style>

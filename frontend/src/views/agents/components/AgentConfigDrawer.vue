<script setup lang="ts">
import { ref, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useToolStore } from '@/stores/tool'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useWorkflowListStore } from '@/stores/workflow'
import { useMcpStore } from '@/stores/mcp'
import { useSkillStore } from '@/stores/skill'
import { useSettingsStore } from '@/stores/settings'
import AgentCapabilityPicker from './AgentCapabilityPicker.vue'
import type { Agent } from '@/types/agent'
import { debugAgentForm, safeCopyAgentData } from '@/utils/agentDebug'

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
const settingsStore = useSettingsStore()

const formData = ref({
  name: '',
  desc: '',
  model: '',
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

// 从系统设置获取 LLM 模型列表
const modelOptions = computed(() => {
  const llmModels = settingsStore.models.llm || []
  return llmModels.map(m => ({
    label: m.name + (m.def ? ' (默认)' : ''),
    value: m.name,
    disabled: !m.enabled
  }))
})

// 获取默认模型名称
const defaultModelName = computed(() => {
  const llmModels = settingsStore.models.llm || []
  const defaultModel = llmModels.find(m => m.def && m.enabled)
  return defaultModel?.name || ''
})

watch(() => props.visible, async (visible) => {
  if (visible) {
    await loadCandidateData()
    if (props.data) {
      // 使用安全的深拷贝初始化
      formData.value = safeCopyAgentData(props.data)
      debugAgentForm(formData.value, '初始化（编辑模式）')
    } else {
      resetForm()
      debugAgentForm(formData.value, '初始化（新建模式）')
    }
  }
})

async function loadCandidateData() {
  try {
    await Promise.all([
      settingsStore.loadModels(),
      toolStore.loadTools().catch(e => {
        console.error('加载工具失败:', e)
      }),
      knowledgeStore.loadKbList().catch(e => {
        console.error('加载知识库列表失败:', e)
      }),
      workflowListStore.loadWorkflows().catch(e => {
        console.error('加载工作流失败:', e)
      }),
      mcpStore.loadMcps().catch(e => {
        console.error('加载 MCP 失败:', e)
      }),
      skillStore.loadSkills().catch(e => {
        console.error('加载技能失败:', e)
      })
    ])
    // 如果有知识库，加载第一个知识库的文档
    const kbList = knowledgeStore.kbList
    if (kbList.length > 0) {
      await knowledgeStore.loadDocuments(kbList[0].id, 1, 100).catch(e => {
        console.error('加载文档列表失败:', e)
      })
    }
  } catch (error) {
    console.error('加载候选数据失败:', error)
  }
}

function resetForm() {
  // 获取默认 LLM 模型
  const defaultModel = settingsStore.getDefaultModel('llm')
  formData.value = {
    name: '',
    desc: '',
    model: defaultModel?.name || '',
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
  console.log('[能力更新] 接收到:', capabilities)
  formData.value.tools = capabilities.tools
  formData.value.docs = capabilities.docs
  formData.value.wfs = capabilities.wfs
  formData.value.mcps = capabilities.mcps
  formData.value.skills = capabilities.skills
  debugAgentForm(formData.value, '能力更新后')
}

function handleSubmit() {
  debugAgentForm(formData.value, '提交前')

  if (!formData.value.name.trim()) {
    ElMessage.warning('请输入智能体名称')
    return
  }

  // 再次验证数据完整性
  const { tools, mcps, skills } = formData.value
  console.log('[提交验证]', { tools: tools?.length, mcps: mcps?.length, skills: skills?.length })

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
            <el-alert
              v-if="formData.model && formData.model !== defaultModelName"
              type="warning"
              :closable="false"
              show-icon
              style="margin-top: 8px"
            >
              <template #title>
                注意：当前选择了非默认模型，请确保该模型的 API Key 有效
              </template>
            </el-alert>
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

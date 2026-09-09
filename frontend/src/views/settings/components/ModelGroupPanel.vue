<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSettingsStore } from '@/stores/settings'
import StatusChip from '@/components/common/StatusChip.vue'
import ModelConfigDialog from './ModelConfigDialog.vue'
import { EmbeddingRebuildAlert } from '@/utils/embeddingRebuildAlert'
import type { ModelGroup, ModelDef } from '@/types/settings'

interface Props {
  group: ModelGroup
}

const props = defineProps<Props>()
const settingsStore = useSettingsStore()

const dialogVisible = ref(false)
const editingModel = ref<ModelDef | null>(null)

// 分组配置
const groupConfigs = {
  llm: {
    title: 'LLM 模型配置',
    description: '配置大语言模型，用于对话生成、摘要提取和问题改写等任务',
    icon: 'ChatDotRound'
  },
  embed: {
    title: 'Embedding 模型配置',
    description: '配置文本向量化模型，用于知识库向量化存储和语义检索',
    icon: 'Box'
  },
  rerank: {
    title: 'Rerank 模型配置',
    description: '配置重排序模型，用于优化检索结果的排序精度',
    icon: 'Sort'
  }
}

const config = computed(() => groupConfigs[props.group])
const models = computed(() => settingsStore.getModelsByGroup(props.group))

function handleCreate() {
  editingModel.value = null
  dialogVisible.value = true
}

function handleEdit(model: ModelDef) {
  editingModel.value = model
  dialogVisible.value = true
}

async function handleSetDefault(model: ModelDef) {
  // 如果是 Embedding 组，弹出重建索引确认
  if (props.group === 'embed') {
    EmbeddingRebuildAlert.show().then(async () => {
      await settingsStore.setDefault(props.group, model.name)
      ElMessage.success('已切换默认模型，需要重建向量索引')
    }).catch(() => {
      // 用户取消
    })
  } else {
    await settingsStore.setDefault(props.group, model.name)
    ElMessage.success('已设为默认模型')
  }
}

async function handleDelete(model: ModelDef) {
  try {
    await ElMessageBox.confirm(
      `确定要删除模型 "${model.name}" 吗？此操作不可恢复。`,
      '删除模型',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await settingsStore.deleteModel(props.group, model.name)
    ElMessage.success('删除成功')
  } catch (error) {
    // 用户取消删除
  }
}

async function handleSubmit(data: ModelDef) {
  if (editingModel.value) {
    await settingsStore.saveModel(props.group, data)
    ElMessage.success('更新成功')
  } else {
    await settingsStore.saveModel(props.group, data)
    ElMessage.success('创建成功')
  }
}

// 辅助函数
function getProviderLabel(prov: string): string {
  const labels: Record<string, string> = {
    dashscope: 'DashScope',
    openai: 'OpenAI',
    ollama: 'Ollama',
    azure: 'Azure',
    vllm: 'vLLM'
  }
  return labels[prov] || prov
}

function getUseLabel(group: ModelGroup, use: string): string {
  const labels: Record<string, Record<string, string>> = {
    llm: {
      qa: '答疑生成',
      summary: '快速摘要',
      rewrite: '问题改写'
    },
    embed: {
      retrieval: '向量召回'
    },
    rerank: {
      rerank: '精排'
    }
  }
  return labels[group]?.[use] || use
}

function formatContext(ctx?: string): string {
  if (!ctx) return '-'
  const num = parseInt(ctx)
  if (num >= 1000) {
    return (num / 1000).toFixed(0) + 'k'
  }
  return ctx
}
</script>

<template>
  <div class="model-group-panel">
    <div class="panel-header">
      <div class="header-info">
        <h3>{{ config.title }}</h3>
        <p class="description">{{ config.description }}</p>
      </div>
      <el-button type="primary" icon="Plus" @click="handleCreate">
        添加模型
      </el-button>
    </div>

    <div v-if="settingsStore.loading" class="loading-state">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <el-empty
      v-else-if="models.length === 0"
      description="暂无模型配置"
      :image-size="120"
    />

    <el-table v-else :data="models" class="models-table">
      <el-table-column prop="name" label="模型名称" min-width="150" />
      <el-table-column prop="prov" label="供应商" width="140">
        <template #default="{ row }">
          {{ getProviderLabel((row as ModelDef).prov) }}
        </template>
      </el-table-column>
      <el-table-column prop="use" label="用途" width="120">
        <template #default="{ row }">
          {{ getUseLabel(group, (row as ModelDef).use) }}
        </template>
      </el-table-column>

      <!-- LLM 组显示温度 -->
      <el-table-column v-if="group === 'llm'" prop="temp" label="温度" width="80" align="center">
        <template #default="{ row }">
          {{ (row as ModelDef).temp?.toFixed(1) }}
        </template>
      </el-table-column>

      <!-- Embedding 组显示维度 -->
      <el-table-column v-if="group === 'embed'" prop="dim" label="维度" width="80" align="center">
        <template #default="{ row }">
          {{ (row as ModelDef).dim }}
        </template>
      </el-table-column>

      <el-table-column prop="ctx" label="上下文" width="90" align="center">
        <template #default="{ row }">
          {{ formatContext((row as ModelDef).ctx) }}
        </template>
      </el-table-column>

      <el-table-column label="默认" width="80" align="center">
        <template #default="{ row }">
          <StatusChip v-if="(row as ModelDef).def" type="ok" label="默认" dot />
          <span v-else class="text-gray">-</span>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="200" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="!(row as ModelDef).def"
            type="primary"
            size="small"
            link
            @click="handleSetDefault(row as ModelDef)"
          >
            设默认
          </el-button>
          <el-button type="primary" size="small" link @click="handleEdit(row as ModelDef)">
            编辑
          </el-button>
          <el-button type="danger" size="small" link @click="handleDelete(row as ModelDef)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <ModelConfigDialog
      v-model:visible="dialogVisible"
      :group="group"
      :data="editingModel"
      @submit="handleSubmit"
    />
  </div>
</template>

<style lang="scss" scoped>
.model-group-panel {
  width: 100%;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.header-info {
  flex: 1;
}

.header-info h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.description {
  margin: 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: #909399;

  p {
    margin-top: 12px;
  }
}

.models-table {
  margin-top: 16px;
}

.text-gray {
  color: #c0c4cc;
}
</style>

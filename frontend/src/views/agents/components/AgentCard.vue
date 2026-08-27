<script setup lang="ts">
import { ref, computed } from 'vue'
import StatusChip from '@/components/common/StatusChip.vue'
import ConfirmDelete from '@/components/common/ConfirmDelete.vue'
import AgentChatDrawer from './AgentChatDrawer.vue'
import type { Agent } from '@/types/agent'

interface Props {
  data: Agent
}

const props = defineProps<Props>()

const emit = defineEmits<{
  config: [agent: Agent]
  delete: [id: string]
  toggle: [id: string, enabled: boolean]
  chat: [agent: Agent]
}>()

const chatDrawerVisible = ref(false)

// 能力类型列表
const capabilityTypes = computed(() => {
  const agent = props.data
  const types = []
  if (agent.tools.length > 0) types.push({ label: '工具', count: agent.tools.length })
  if (agent.docs.length > 0) types.push({ label: '文档', count: agent.docs.length })
  if (agent.wfs.length > 0) types.push({ label: '工作流', count: agent.wfs.length })
  if (agent.mcps.length > 0) types.push({ label: 'MCP', count: agent.mcps.length })
  if (agent.skills.length > 0) types.push({ label: '技能', count: agent.skills.length })
  return types
})

function handleConfig() {
  emit('config', props.data)
}

function handleChat() {
  chatDrawerVisible.value = true
}

function handleToggle(val: string | number | boolean) {
  const enabled = Boolean(val)
  emit('toggle', props.data.id, enabled)
}

function handleDelete() {
  emit('delete', props.data.id)
}
</script>

<template>
  <div class="agent-card">
    <div class="agent-header">
      <div class="agent-model">
        <StatusChip type="run" :label="data.model" />
      </div>
      <el-switch
        :model-value="data.enabled"
        @update:model-value="handleToggle"
        size="small"
      />
    </div>

    <div class="agent-content">
      <h3 class="agent-name">{{ data.name }}</h3>
      <p class="agent-desc">{{ data.desc }}</p>

      <!-- 挂载能力徽标 -->
      <div v-if="capabilityTypes.length > 0" class="agent-capabilities">
        <div v-for="(cap, index) in capabilityTypes" :key="index" class="capability-item">
          <el-tag size="small" type="info">{{ cap.label }} × {{ cap.count }}</el-tag>
        </div>
      </div>
      <div v-else class="agent-capabilities">
        <el-tag size="small" type="info">未挂载能力</el-tag>
      </div>

      <div class="agent-meta">
        <span class="meta-item">
          <el-icon><Clock /></el-icon>
          最近活跃: {{ data.lastActive }}
        </span>
      </div>
    </div>

    <div class="agent-actions">
      <el-button size="small" icon="Setting" @click="handleConfig">
        配置
      </el-button>
      <el-button size="small" icon="ChatDotRound" @click="handleChat">
        对话
      </el-button>
      <ConfirmDelete @confirm="handleDelete" />
    </div>

    <!-- 对话抽屉 -->
    <AgentChatDrawer
      v-model:visible="chatDrawerVisible"
      :agent="data"
    />
  </div>
</template>

<style lang="scss" scoped>
.agent-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.3s;
  display: flex;
  flex-direction: column;
  gap: 12px;

  &:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  }
}

.agent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.agent-content {
  flex: 1;
}

.agent-name {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.agent-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
  min-height: 40px;
}

.agent-capabilities {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.agent-meta {
  display: flex;
  font-size: 12px;
  color: #909399;

  .meta-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.agent-actions {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}
</style>
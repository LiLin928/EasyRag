<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '@/stores/agent'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AgentCard from './components/AgentCard.vue'
import AgentConfigDrawer from './components/AgentConfigDrawer.vue'
import type { Agent } from '@/types/agent'

const agentStore = useAgentStore()

const drawerVisible = ref(false)
const editingAgent = ref<Agent | null>(null)

onMounted(() => {
  agentStore.loadAgents()
})

function handleCreate() {
  editingAgent.value = null
  drawerVisible.value = true
}

function handleConfig(agent: Agent) {
  editingAgent.value = agent
  drawerVisible.value = true
}

async function handleToggle(id: string, enabled: boolean) {
  try {
    await agentStore.toggleAgent(id, enabled)
    ElMessage.success(enabled ? '已启用' : '已禁用')
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

async function handleDelete(id: string) {
  try {
    await agentStore.deleteAgent(id)
    ElMessage.success('删除成功')
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

async function handleSubmit(data: Partial<Agent>) {
  if (editingAgent.value) {
    await agentStore.updateAgent(editingAgent.value.id, data)
    ElMessage.success('更新成功')
  } else {
    await agentStore.createAgent(data)
    ElMessage.success('创建成功')
  }
  drawerVisible.value = false
}

function handleChat(agent: Agent) {
  editingAgent.value = agent
}
</script>

<template>
  <div class="agents-view">
    <PageHeader title="智能体管理" subtitle="装配自定义工具/知识库/工作流/MCP/技能，组合成可对话的专属助手">
      <template #actions>
        <el-input
          v-model="agentStore.keyword"
          placeholder="搜索智能体"
          prefix-icon="Search"
          clearable
          style="width: 240px"
        />
        <el-button type="primary" icon="Plus" @click="handleCreate">
          新建智能体
        </el-button>
      </template>
    </PageHeader>

    <div v-if="agentStore.loading" class="loading-state">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <EmptyState
      v-else-if="agentStore.filteredAgents.length === 0"
      icon="User"
      :text="agentStore.keyword ? '未找到匹配的智能体' : '暂无智能体'"
    >
      <template #action>
        <el-button v-if="!agentStore.keyword" type="primary" @click="handleCreate">
          新建智能体
        </el-button>
      </template>
    </EmptyState>

    <div v-else class="agents-grid">
      <AgentCard
        v-for="agent in agentStore.filteredAgents"
        :key="agent.id"
        :data="agent"
        @config="handleConfig"
        @delete="handleDelete"
        @toggle="handleToggle"
        @chat="handleChat"
      />
    </div>

    <AgentConfigDrawer
      v-model:visible="drawerVisible"
      :data="editingAgent"
      @submit="handleSubmit"
    />
  </div>
</template>

<style lang="scss" scoped>
.agents-view {
  padding: 0;
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

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-top: 16px;
}
</style>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useMcpStore } from '@/stores/mcp'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import McpCard from './components/McpCard.vue'
import McpConfigDialog from './components/McpConfigDialog.vue'
import McpTestResult from './components/McpTestResult.vue'
import type { Mcp } from '@/types/mcp'

const mcpStore = useMcpStore()

const dialogVisible = ref(false)
const testVisible = ref(false)
const editingMcp = ref<Mcp | null>(null)
const testingMcp = ref<Mcp | null>(null)

onMounted(() => {
  mcpStore.loadMcps()
})

function handleCreate() {
  editingMcp.value = null
  dialogVisible.value = true
}

function handleConfig(mcp: Mcp) {
  editingMcp.value = mcp
  dialogVisible.value = true
}

function handleTest(mcp: Mcp) {
  testingMcp.value = mcp
  testVisible.value = true
}

async function handleToggle(id: string, status: 'on' | 'off') {
  try {
    await mcpStore.toggleMcp(id, status)
    ElMessage.success(status === 'on' ? 'MCP 服务已启动' : 'MCP 服务已停止')
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

async function handleDelete(id: string) {
  try {
    await mcpStore.deleteMcp(id)
    ElMessage.success('删除成功')
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

async function handleSubmit(data: Partial<Mcp>) {
  if (editingMcp.value) {
    await mcpStore.updateMcp(editingMcp.value.id, data)
    ElMessage.success('更新成功')
  } else {
    await mcpStore.createMcp(data)
    ElMessage.success('创建成功')
  }
}
</script>

<template>
  <div class="mcp-view">
    <PageHeader title="MCP 服务管理" subtitle="管理 Model Context Protocol 服务，支持 stdio 和 SSE 两种连接方式">
      <template #actions>
        <el-input
          v-model="mcpStore.keyword"
          placeholder="搜索 MCP 服务"
          prefix-icon="Search"
          clearable
          style="width: 240px"
        />
        <el-button type="primary" icon="Plus" @click="handleCreate">
          添加 MCP
        </el-button>
      </template>
    </PageHeader>

    <div v-if="mcpStore.loading" class="loading-state">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <EmptyState
      v-else-if="mcpStore.filteredMcps.length === 0"
      icon="Connection"
      :text="mcpStore.keyword ? '未找到匹配的 MCP 服务' : '暂无 MCP 服务'"
    >
      <template #action>
        <el-button v-if="!mcpStore.keyword" type="primary" @click="handleCreate">添加 MCP</el-button>
      </template>
    </EmptyState>

    <div v-else class="mcps-grid">
      <McpCard
        v-for="mcp in mcpStore.filteredMcps"
        :key="mcp.id"
        :data="mcp"
        @config="handleConfig"
        @test="handleTest"
        @delete="handleDelete"
        @toggle="handleToggle"
      />
    </div>

    <McpConfigDialog
      v-model:visible="dialogVisible"
      :data="editingMcp"
      @submit="handleSubmit"
    />

    <McpTestResult
      v-model:visible="testVisible"
      :mcp="testingMcp"
    />
  </div>
</template>

<style lang="scss" scoped>
.mcp-view {
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

.mcps-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-top: 16px;
}
</style>

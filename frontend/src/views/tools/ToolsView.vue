<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useToolStore } from '@/stores/tool'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ToolCard from './components/ToolCard.vue'
import ToolConfigDialog from './components/ToolConfigDialog.vue'
import ToolTestPanel from './components/ToolTestPanel.vue'
import type { Tool } from '@/types/tool'

const toolStore = useToolStore()

const dialogVisible = ref(false)
const testVisible = ref(false)
const editingTool = ref<Tool | null>(null)
const testingTool = ref<Tool | null>(null)

onMounted(() => {
  toolStore.loadTools()
})

function handleCreate() {
  editingTool.value = null
  dialogVisible.value = true
}

function handleConfig(tool: Tool) {
  editingTool.value = tool
  dialogVisible.value = true
}

function handleTest(tool: Tool) {
  testingTool.value = tool
  testVisible.value = true
}

async function handleToggle(id: string, enabled: boolean) {
  try {
    await toolStore.toggleTool(id, enabled)
    ElMessage.success(enabled ? '工具已启用' : '工具已停用')
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

async function handleDelete(id: string) {
  try {
    await toolStore.deleteTool(id)
    ElMessage.success('删除成功')
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

async function handleSubmit(data: Partial<Tool>) {
  if (editingTool.value) {
    await toolStore.updateTool(editingTool.value.id, data)
    ElMessage.success('更新成功')
  } else {
    await toolStore.createTool(data)
    ElMessage.success('创建成功')
  }
}
</script>

<template>
  <div class="tools-view">
    <PageHeader title="工具管理" subtitle="管理可被智能体和工作流调用的外部能力">
      <template #actions>
        <el-input
          v-model="toolStore.keyword"
          placeholder="搜索工具"
          prefix-icon="Search"
          clearable
          style="width: 240px"
        />
        <el-button type="primary" icon="Plus" @click="handleCreate">
          新建工具
        </el-button>
      </template>
    </PageHeader>

    <div v-if="toolStore.loading" class="loading-state">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <EmptyState
      v-else-if="toolStore.filteredTools.length === 0"
      icon="Tools"
      :text="toolStore.keyword ? '未找到匹配的工具' : '暂无工具'"
    >
      <template #action>
        <el-button v-if="!toolStore.keyword" type="primary" @click="handleCreate">新建工具</el-button>
      </template>
    </EmptyState>

    <div v-else class="tools-grid">
      <ToolCard
        v-for="tool in toolStore.filteredTools"
        :key="tool.id"
        :data="tool"
        @config="handleConfig"
        @test="handleTest"
        @delete="handleDelete"
        @toggle="handleToggle"
      />
    </div>

    <ToolConfigDialog
      v-model:visible="dialogVisible"
      :data="editingTool"
      @submit="handleSubmit"
    />

    <ToolTestPanel
      v-model:visible="testVisible"
      :tool="testingTool"
    />
  </div>
</template>

<style lang="scss" scoped>
.tools-view {
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

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-top: 16px;
}
</style>

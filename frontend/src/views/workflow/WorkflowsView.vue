<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkflowListStore } from '@/stores/workflow'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import WorkflowCard from './components/WorkflowCard.vue'
import TemplateCard from './components/TemplateCard.vue'
import ExecutionHistory from './components/ExecutionHistory.vue'

const router = useRouter()
const store = useWorkflowListStore()

onMounted(() => {
  store.loadWorkflows()
  store.loadTemplates()
  store.loadHistory()
})

function handleCreate() {
  // 新建流程 -> 进入编辑器
  router.push('/workflows/editor/new')
}

function handleTabChange(_tab: string | number) {
  store.activeTab = _tab as any
}
</script>

<template>
  <div class="workflows-view">
    <PageHeader title="工作流" subtitle="可视化编排智能体执行流程，支持模板复用与人工介入">
      <template #actions>
        <el-input
          v-if="store.activeTab === 'list'"
          v-model="store.keyword"
          placeholder="搜索流程"
          prefix-icon="Search"
          clearable
          style="width: 240px"
        />
        <el-input
          v-else-if="store.activeTab === 'templates'"
          v-model="store.tplKeyword"
          placeholder="搜索模板"
          prefix-icon="Search"
          clearable
          style="width: 240px"
        />
        <el-button type="primary" icon="Plus" @click="handleCreate">
          新建流程
        </el-button>
      </template>
    </PageHeader>

    <!-- Tab 切换 -->
    <el-tabs v-model="store.activeTab" class="workflow-tabs" @tab-change="handleTabChange">
      <el-tab-pane name="list">
        <template #label>
          <span class="tab-label">
            流程
            <el-badge v-if="store.workflows.length > 0" :value="store.workflows.length" class="tab-badge" />
          </span>
        </template>

        <!-- 加载状态 -->
        <div v-if="store.loading" class="loading-state">
          <el-icon class="is-loading" :size="32"><Loading /></el-icon>
          <p>加载中...</p>
        </div>

        <!-- 空状态 -->
        <EmptyState
          v-else-if="store.filteredWorkflows.length === 0"
          icon="Share"
          :text="store.keyword ? '未找到匹配的流程' : '暂无流程'"
        >
          <template #action>
            <el-button v-if="!store.keyword" type="primary" @click="handleCreate">新建流程</el-button>
          </template>
        </EmptyState>

        <!-- 流程网格 -->
        <div v-else class="card-grid">
          <WorkflowCard
            v-for="wf in store.filteredWorkflows"
            :key="wf.id"
            :data="wf"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="模板市场" name="templates">
        <EmptyState
          v-if="store.filteredTemplates.length === 0"
          icon="Files"
          :text="store.tplKeyword ? '未找到匹配的模板' : '暂无模板'"
        />
        <div v-else class="card-grid">
          <TemplateCard
            v-for="tpl in store.filteredTemplates"
            :key="tpl.id"
            :data="tpl"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="执行历史" name="history">
        <ExecutionHistory :data="store.history" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style lang="scss" scoped>
.workflows-view {
  padding: 0;
}

.workflow-tabs {
  margin-bottom: 8px;

  :deep(.tab-label) {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  :deep(.tab-badge) {
    .el-badge__content {
      background-color: #409eff;
    }
  }
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

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-top: 16px;
}
</style>

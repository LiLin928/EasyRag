<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkflowListStore } from '@/stores/workflow'
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
    <div class="view-header">
      <h2>工作流</h2>
      <el-button type="primary" icon="Plus" @click="handleCreate">
        新建流程
      </el-button>
    </div>
    
    <el-tabs v-model="store.activeTab" class="workflow-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="流程" name="list">
        <div class="card-grid">
          <WorkflowCard
            v-for="wf in store.workflows"
            :key="wf.id"
            :data="wf"
          />
        </div>
        <el-empty v-if="store.workflows.length === 0" description="暂无流程" />
      </el-tab-pane>
      
      <el-tab-pane label="模板市场" name="templates">
        <div class="card-grid">
          <TemplateCard
            v-for="tpl in store.templates"
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
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  
  h2 {
    margin: 0;
    font-size: 18px;
    color: #303133;
  }
}

.workflow-tabs {
  flex: 1;
  margin: 16px 24px;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  
  :deep(.el-tabs__header) {
    margin: 0;
    padding: 0 16px;
    background: #fafafa;
  }
  
  :deep(.el-tabs__content) {
    height: calc(100% - 40px);
    overflow: auto;
  }
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  padding: 16px;
}
</style>



<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useTodoStore } from '@/stores/todo'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import TodoItem from './components/TodoItem.vue'
import TodoDetail from './components/TodoDetail.vue'

const todoStore = useTodoStore()

const activeTab = ref<'pending' | 'done'>('pending')
const selectedTodoId = ref<string | null>(null)

// 当前选中的待办
const selectedTodo = computed(() => {
  if (!selectedTodoId.value) return null
  return todoStore.todos.find(t => t.id === selectedTodoId.value) || null
})

// 待处理待办列表
const pendingTodos = computed(() => {
  return todoStore.todos.filter(t => t.status === 'pending')
})

// 已完成待办列表
const completedTodos = computed(() => {
  return todoStore.todos.filter(t => t.status === 'done' || t.status === 'rejected')
})

// 当前显示的待办列表
const displayTodos = computed(() => {
  return activeTab.value === 'pending' ? pendingTodos.value : completedTodos.value
})

onMounted(() => {
  loadTodos()
})

async function loadTodos() {
  try {
    await todoStore.loadTodos()
  } catch (error) {
    ElMessage.error('加载待办列表失败')
  }
}

function handleTabChange(tabName: string | number) {
  // 确保 tabName 是字符串类型
  const tabNameStr = String(tabName) as 'pending' | 'done'
  if (tabNameStr === 'pending' || tabNameStr === 'done') {
    activeTab.value = tabNameStr
    // 切换Tab时清除选中状态
    selectedTodoId.value = null
  }
}

function handleSelectTodo(todoId: string) {
  selectedTodoId.value = todoId
}

async function handleSubmit(todoId: string, formData: Record<string, unknown>) {
  try {
    await todoStore.submitTodo(todoId, formData)
    ElMessage.success('提交成功')
    selectedTodoId.value = null
  } catch (error) {
    ElMessage.error('提交失败')
  }
}

async function handleReject(todoId: string) {
  try {
    await todoStore.rejectTodo(todoId)
    ElMessage.success('已驳回')
    selectedTodoId.value = null
  } catch (error) {
    ElMessage.error('驳回失败')
  }
}

function handleCloseDetail() {
  selectedTodoId.value = null
}
</script>

<template>
  <div class="todos-view">
    <PageHeader title="待办中心" subtitle="工作流人工介入节点产生的待办事项，包含动态表单与超时倒计时" />

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" @tab-change="handleTabChange" class="todos-tabs">
      <el-tab-pane label="待处理" name="pending">
        <template #label>
          <span class="tab-label">
            待处理
            <el-badge v-if="pendingTodos.length > 0" :value="pendingTodos.length" class="tab-badge" />
          </span>
        </template>
      </el-tab-pane>
      <el-tab-pane label="已完成" name="done">
        <template #label>
          <span class="tab-label">
            已完成
            <el-badge v-if="completedTodos.length > 0" :value="completedTodos.length" class="tab-badge" />
          </span>
        </template>
      </el-tab-pane>
    </el-tabs>

    <!-- 加载状态 -->
    <div v-if="todoStore.loading" class="loading-state">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <!-- 空状态 -->
    <EmptyState
      v-else-if="displayTodos.length === 0"
      icon="List"
      :text="activeTab === 'pending' ? '暂无待处理事项' : '暂无已完成事项'"
    />

    <!-- 待办列表 -->
    <div v-else class="todos-content">
      <div class="todos-list">
        <TodoItem
          v-for="todo in displayTodos"
          :key="todo.id"
          :data="todo"
          :active="selectedTodoId === todo.id"
          @select="handleSelectTodo"
        />
      </div>

      <!-- 待办详情 -->
      <div v-if="selectedTodo" class="todos-detail">
        <TodoDetail
          :data="selectedTodo"
          @submit="handleSubmit"
          @reject="handleReject"
          @close="handleCloseDetail"
        />
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.todos-view {
  padding: 0;
}

.todos-tabs {
  margin-bottom: 20px;

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

.todos-content {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 20px;
  align-items: start;
}

.todos-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.todos-detail {
  position: sticky;
  top: 0;
}

@media (max-width: 1200px) {
  .todos-content {
    grid-template-columns: 1fr;
  }

  .todos-detail {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 400px;
    z-index: 1000;
    box-shadow: -4px 0 16px rgba(0, 0, 0, 0.15);
  }
}
</style>
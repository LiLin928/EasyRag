<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import KbCard from './components/KbCard.vue'
import KbFormDialog from './components/KbFormDialog.vue'
import type { KnowledgeBase } from '@/types/knowledge'

const knowledgeStore = useKnowledgeStore()

const searchKeyword = ref('')
const dialogVisible = ref(false)
const editingKb = ref<KnowledgeBase | null>(null)

onMounted(() => {
  knowledgeStore.loadKbList()
})

function handleSearch() {
  knowledgeStore.loadKbList(searchKeyword.value)
}

async function handleCreate() {
  editingKb.value = null
  dialogVisible.value = true
}

function handleEdit(kb: KnowledgeBase) {
  editingKb.value = kb
  dialogVisible.value = true
}

async function handleDelete(id: string) {
  try {
    await ElMessageBox.confirm('删除知识库将同时删除其中的所有文档，确定要删除吗？', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await knowledgeStore.deleteKb(id)
    ElMessage.success('删除成功')
  } catch (error) {
    // 取消删除
  }
}

async function handleSubmit(data: Partial<KnowledgeBase>) {
  if (editingKb.value) {
    await knowledgeStore.updateKb(editingKb.value.id, data)
    ElMessage.success('更新成功')
  } else {
    await knowledgeStore.createKb(data)
    ElMessage.success('创建成功')
  }
}
</script>

<template>
  <div class="knowledge-list-view">
    <PageHeader title="知识库管理" subtitle="管理知识库和文档">
      <template #actions>
        <el-input
          v-model="searchKeyword"
          placeholder="搜索知识库"
          prefix-icon="Search"
          clearable
          style="width: 240px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-button type="primary" icon="Plus" @click="handleCreate">
          新建知识库
        </el-button>
      </template>
    </PageHeader>
    
    <div v-if="knowledgeStore.kbLoading" class="loading-state">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>
    
    <EmptyState
      v-else-if="knowledgeStore.kbList.length === 0"
      icon="Folder"
      text="暂无知识库"
    >
      <template #action>
        <el-button type="primary" @click="handleCreate">新建知识库</el-button>
      </template>
    </EmptyState>
    
    <div v-else class="kb-grid">
      <KbCard
        v-for="kb in knowledgeStore.kbList"
        :key="kb.id"
        :data="kb"
        @edit="handleEdit"
        @delete="handleDelete"
      />
    </div>
    
    <KbFormDialog
      v-model:visible="dialogVisible"
      :data="editingKb"
      @submit="handleSubmit"
    />
  </div>
</template>

<style lang="scss" scoped>
.knowledge-list-view {
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

.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-top: 16px;
}
</style>

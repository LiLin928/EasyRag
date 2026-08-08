<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useKnowledgeStore } from '@/stores/knowledge'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import UploadPanel from './components/UploadPanel.vue'
import DocumentTable from './components/DocumentTable.vue'

const route = useRoute()
const router = useRouter()
const knowledgeStore = useKnowledgeStore()

const kbId = ref(route.params.kbId as string)

// 监听路由变化
watch(() => route.params.kbId, (newId) => {
  if (newId) {
    kbId.value = newId as string
    loadKbAndDocs()
  }
})

onMounted(() => {
  loadKbAndDocs()
})

async function loadKbAndDocs() {
  await knowledgeStore.loadKbDetail(kbId.value)
  await knowledgeStore.loadDocuments(kbId.value)
}

function handleUploaded() {
  knowledgeStore.loadDocuments(kbId.value)
}

function handleBack() {
  router.push('/knowledge')
}
</script>

<template>
  <div class="kb-detail-view">
    <PageHeader :title="knowledgeStore.currentKb?.name || '知识库详情'">
      <template #subtitle>
        <span v-if="knowledgeStore.currentKb">
          {{ knowledgeStore.currentKb.docCount }} 篇文档 · {{ knowledgeStore.currentKb.totalSize }}
        </span>
      </template>
      <template #actions>
        <el-button icon="ArrowLeft" @click="handleBack">返回列表</el-button>
      </template>
    </PageHeader>
    
    <!-- 知识库信息条 -->
    <div v-if="knowledgeStore.currentKb" class="kb-info-bar">
      <p class="kb-desc">{{ knowledgeStore.currentKb.desc }}</p>
      <el-tag v-if="knowledgeStore.currentKb.scene" size="small" type="info">
        {{ knowledgeStore.currentKb.scene }}
      </el-tag>
    </div>
    
    <!-- 上传区 -->
    <UploadPanel :kbId="kbId" @uploaded="handleUploaded" />
    
    <!-- 文档列表 -->
    <div class="doc-section">
      <h3 class="section-title">文档列表</h3>
      
      <EmptyState
        v-if="!knowledgeStore.docLoading && knowledgeStore.docList.length === 0"
        icon="Document"
        text="暂无文档"
      >
        <template #action>
          <span class="empty-hint">上传文档开始使用</span>
        </template>
      </EmptyState>
      
      <DocumentTable v-else :kbId="kbId" />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.kb-detail-view {
  padding: 0;
}

.kb-info-bar {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  
  .kb-desc {
    margin: 0;
    color: #606266;
    font-size: 14px;
  }
}

.doc-section {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  
  .section-title {
    margin: 0 0 16px;
    font-size: 16px;
    font-weight: 600;
    color: #303133;
  }
}

.empty-hint {
  color: #909399;
  font-size: 13px;
}
</style>

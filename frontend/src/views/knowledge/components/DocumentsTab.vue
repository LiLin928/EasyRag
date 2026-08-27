<script setup lang="ts">
import { onMounted } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import EmptyState from '@/components/common/EmptyState.vue'
import UploadPanel from './UploadPanel.vue'
import DocumentTable from './DocumentTable.vue'

const props = defineProps<{ kbId: string }>()
const knowledgeStore = useKnowledgeStore()

onMounted(() => {
  knowledgeStore.loadDocuments(props.kbId)
})

function handleUploaded() {
  knowledgeStore.loadDocuments(props.kbId)
}
</script>

<template>
  <div class="documents-tab">
    <UploadPanel :kbId="kbId" @uploaded="handleUploaded" />

    <div class="doc-section">
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
.doc-section {
  margin-top: 16px;
}

.empty-hint {
  color: #909399;
  font-size: 13px;
}
</style>

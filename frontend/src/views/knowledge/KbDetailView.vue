<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useKnowledgeStore } from '@/stores/knowledge'
import PageHeader from '@/components/common/PageHeader.vue'
import DocumentsTab from './components/DocumentsTab.vue'
import SegmentsTab from './components/SegmentsTab.vue'
import MetadataTab from './components/MetadataTab.vue'
import RetrievalTestTab from './components/RetrievalTestTab.vue'
import SettingsTab from './components/SettingsTab.vue'

const route = useRoute()
const router = useRouter()
const knowledgeStore = useKnowledgeStore()

const kbId = ref(route.params.kbId as string)
const activeTab = ref('settings')

watch(() => route.params.kbId, (newId) => {
  if (newId) {
    kbId.value = newId as string
    loadKb()
  }
})

onMounted(() => {
  loadKb()
})

async function loadKb() {
  await knowledgeStore.loadKbDetail(kbId.value)
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

    <div v-if="knowledgeStore.currentKb" class="kb-info-bar">
      <p class="kb-desc">{{ knowledgeStore.currentKb.desc }}</p>
      <div class="kb-tags">
        <el-tag v-if="knowledgeStore.currentKb.scene" size="small" type="info">
          {{ knowledgeStore.currentKb.scene }}
        </el-tag>
        <el-tag v-if="knowledgeStore.currentKb.embeddingModel" size="small">
          Embedding: {{ knowledgeStore.currentKb.embeddingModel }}
        </el-tag>
        <el-tag v-if="knowledgeStore.currentKb.rerankModel" size="small" type="warning">
          Rerank: {{ knowledgeStore.currentKb.rerankModel }}
        </el-tag>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="kb-tabs">
      <el-tab-pane label="设置" name="settings">
        <SettingsTab :kbId="kbId" />
      </el-tab-pane>
      <el-tab-pane label="文档" name="documents">
        <DocumentsTab :kbId="kbId" />
      </el-tab-pane>
      <el-tab-pane label="元数据" name="metadata">
        <MetadataTab :kbId="kbId" />
      </el-tab-pane>
      <el-tab-pane label="分段" name="segments">
        <SegmentsTab :kbId="kbId" />
      </el-tab-pane>
      <el-tab-pane label="召回测试" name="retrieval-test">
          <RetrievalTestTab :kbId="kbId" />
        </el-tab-pane>
      </el-tabs>
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
  gap: 12px;

  .kb-desc {
    margin: 0;
    color: #606266;
    font-size: 14px;
    flex: 1;
  }

  .kb-tags {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }
}

.kb-tabs {
  background: #fff;
  border-radius: 8px;
  padding: 0 20px 20px;

  :deep(.el-tabs__header) {
    margin-bottom: 16px;
  }
}
</style>

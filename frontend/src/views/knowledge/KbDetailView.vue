<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useKnowledgeStore } from '@/stores/knowledge'
import PageHeader from '@/components/common/PageHeader.vue'
import DocumentsTab from './components/DocumentsTab.vue'
import SegmentsTab from './components/SegmentsTab.vue'
import MetadataTab from './components/MetadataTab.vue'
import RetrievalSettingsTab from './components/RetrievalSettingsTab.vue'
import RetrievalTestingTab from './components/RetrievalTestingTab.vue'

const route = useRoute()
const router = useRouter()
const knowledgeStore = useKnowledgeStore()

const tabs = ['documents', 'segments', 'metadata', 'testing', 'settings'] as const
type KnowledgeTab = (typeof tabs)[number]

const kbId = computed(() => String(route.params.kbId || ''))
const activeTab = computed<KnowledgeTab>({
  get: () => knowledgeStore.activeTab,
  set: (value) => {
    knowledgeStore.activeTab = value
  }
})

const subtitle = computed(() => {
  const kb = knowledgeStore.currentKb
  if (!kb) return '加载中...'
  const description = kb.description || '暂无描述'
  const testTime = kb.last_test_at ? formatTime(kb.last_test_at) : '暂无测试'
  return `${description} · ${kb.doc_count} 篇文档 · ${kb.chunk_count} 个分段 · 最近测试 ${testTime}`
})

function isTab(value: unknown): value is KnowledgeTab {
  return typeof value === 'string' && tabs.includes(value as KnowledgeTab)
}

function initialTab(): KnowledgeTab {
  return isTab(route.query.tab) ? route.query.tab : 'documents'
}

function formatTime(value: string): string {
  return value.replace('T', ' ').slice(0, 16)
}

async function loadKnowledgeBase(): Promise<void> {
  const requestedTab = initialTab()
  knowledgeStore.reset(kbId.value)
  knowledgeStore.activeTab = requestedTab
  await Promise.all([
    knowledgeStore.loadKbDetail(kbId.value),
    knowledgeStore.loadDocuments(kbId.value, 1, 20, { sort: 'created_desc' }),
    knowledgeStore.loadMetadataFields(kbId.value)
  ])
}

watch(
  kbId,
  (value, oldValue) => {
    if (!value || value === oldValue) return
    void loadKnowledgeBase()
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  knowledgeStore.reset()
})

watch(activeTab, (value) => {
  if (route.query.tab === value) return
  void router.replace({ query: { ...route.query, tab: value } })
})

watch(
  () => route.query.tab,
  (value) => {
    if (isTab(value) && value !== activeTab.value) activeTab.value = value
  }
)

function goBack(): void {
  router.push('/knowledge')
}

function goUpload(): void {
  activeTab.value = 'documents'
}

function goTesting(): void {
  activeTab.value = 'testing'
}
</script>

<template>
  <div class="kb-detail-view">
    <div class="sticky-header">
      <PageHeader :title="knowledgeStore.currentKb?.name || '知识库详情'" :subtitle="subtitle">
        <template #actions>
          <el-button icon="ArrowLeft" @click="goBack">返回列表</el-button>
          <el-button type="primary" icon="Upload" @click="goUpload">上传文档</el-button>
          <el-button type="primary" icon="VideoPlay" @click="goTesting">运行测试</el-button>
        </template>
      </PageHeader>
    </div>

    <el-tabs v-model="activeTab" class="kb-tabs">
      <el-tab-pane label="文档" name="documents" lazy>
        <DocumentsTab v-if="activeTab === 'documents'" :kb-id="kbId" />
      </el-tab-pane>
      <el-tab-pane label="分段" name="segments" lazy>
        <SegmentsTab v-if="activeTab === 'segments'" :kb-id="kbId" />
      </el-tab-pane>
      <el-tab-pane label="元数据" name="metadata" lazy>
        <MetadataTab v-if="activeTab === 'metadata'" :kb-id="kbId" />
      </el-tab-pane>
      <el-tab-pane label="召回测试" name="testing" lazy>
        <RetrievalTestingTab v-if="activeTab === 'testing'" :kb-id="kbId" />
      </el-tab-pane>
      <el-tab-pane label="设置" name="settings" lazy>
        <RetrievalSettingsTab v-if="activeTab === 'settings'" :kb-id="kbId" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style lang="scss" scoped>
.kb-detail-view {
  min-width: 0;
}

.sticky-header {
  position: sticky;
  top: 0;
  z-index: 10;
  padding: 0 0 12px;
  background: var(--app-content-bg);

  :deep(.page-header) {
    margin-bottom: 0;
    align-items: flex-start;
    gap: 12px;
  }

  :deep(.header-left) {
    min-width: 0;
    flex-wrap: wrap;
    align-items: flex-start;
  }

  :deep(.subtitle) {
    min-width: 0;
    max-width: 720px;
    line-height: 1.5;
  }
}

.kb-tabs {
  background: transparent;

  :deep(.el-tabs__header) {
    margin: 0 0 16px;
    background: var(--el-bg-color);
    border-radius: 8px 8px 0 0;
    padding: 0 12px;
  }

  :deep(.el-tabs__content) {
    overflow: visible;
  }
}

.testing-placeholder {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 40px 16px;
}

@media (max-width: 768px) {
  .sticky-header {
    :deep(.page-header),
    :deep(.header-left),
    :deep(.header-right) {
      flex-direction: column;
      align-items: stretch;
    }

    :deep(.subtitle),
    :deep(.header-right) {
      max-width: 100%;
      width: 100%;
    }

    :deep(.header-right) {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 6px;

      .el-button {
        margin-left: 0;
        width: 100%;
      }
    }
  }
}
</style>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useKnowledgeStore } from '@/stores/knowledge'
import * as kbApi from '@/api/knowledge'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusChip from '@/components/common/StatusChip.vue'
import FileIcon from '@/components/common/FileIcon.vue'
import TreeBrowser from './TreeBrowser.vue'
import ElementList from './ElementList.vue'
import type { TreeNode } from '@/types/knowledge'

const route = useRoute()
const router = useRouter()
const knowledgeStore = useKnowledgeStore()

const kbId = ref(route.params.kbId as string)
const docId = ref(route.params.docId as string)
const selectedNode = ref<TreeNode | null>(null)

// 监听路由变化
watch(() => route.params, (params) => {
  if (params.kbId && params.docId) {
    kbId.value = params.kbId as string
    docId.value = params.docId as string
    loadDocData()
  }
}, { immediate: true })

onMounted(() => {
  loadDocData()
})

async function loadDocData() {
  // 加载文档信息
  const doc = await kbApi.getDocumentDetail(docId.value)
  knowledgeStore.currentDoc = doc
  
  // 加载结构树
  await knowledgeStore.loadTree(docId.value)
  
  // 加载全部元素
  await knowledgeStore.loadElements(docId.value)
}

function handleNodeSelect(node: TreeNode) {
  selectedNode.value = node
}

function handleBack() {
  router.push('/knowledge/' + kbId.value)
}
</script>

<template>
  <div class="doc-detail-view">
    <PageHeader :title="knowledgeStore.currentDoc?.name || '文档详情'">
      <template #subtitle>
        <span v-if="knowledgeStore.currentDoc" class="doc-meta">
          <FileIcon :ext="knowledgeStore.currentDoc.ext" :size="20" />
          {{ knowledgeStore.currentDoc.size }} · {{ knowledgeStore.currentDoc.pages }} 页
          <StatusChip
            :type="knowledgeStore.currentDoc.status === 'done' ? 'ok' : 'run'"
            :label="knowledgeStore.currentDoc.status === 'done' ? '已完成' : '解析中'"
          />
        </span>
      </template>
      <template #actions>
        <el-button icon="ArrowLeft" @click="handleBack">返回列表</el-button>
      </template>
    </PageHeader>
    
    <div class="doc-content">
      <!-- 左侧结构树 -->
      <div class="tree-panel">
        <div class="panel-header">
          <h4>文档结构</h4>
        </div>
        <TreeBrowser
          v-if="knowledgeStore.tree.length > 0"
          :data="knowledgeStore.tree"
          @select="handleNodeSelect"
        />
        <el-empty v-else description="暂无结构数据" />
      </div>
      
      <!-- 右侧元素列表 -->
      <div class="element-panel">
        <ElementList
          :docId="docId"
          :selectedNode="selectedNode"
        />
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.doc-detail-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
  font-size: 14px;
}

.doc-content {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
  margin-top: 16px;
}

.tree-panel {
  width: 320px;
  background: #fff;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  
  .panel-header {
    padding: 16px;
    border-bottom: 1px solid #ebeef5;
    
    h4 {
      margin: 0;
      font-size: 14px;
      color: #303133;
    }
  }
}

.element-panel {
  flex: 1;
  background: #f5f7fa;
  border-radius: 8px;
  overflow: hidden;
}
</style>

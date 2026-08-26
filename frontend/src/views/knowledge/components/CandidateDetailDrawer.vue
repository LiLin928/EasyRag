<script setup lang="ts">
import { computed } from 'vue'
import type { RetrievalCandidate, RetrievalTestCase } from '@/types/knowledge'
import { useKnowledgeStore } from '@/stores/knowledge'
import FileIcon from '@/components/common/FileIcon.vue'

const props = defineProps<{
  modelValue: boolean
  candidate: RetrievalCandidate | null
  testCase: RetrievalTestCase | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const knowledgeStore = useKnowledgeStore()

const docNameMap = computed(() => {
  const map = new Map<string, string>()
  for (const result of knowledgeStore.runResults) {
    for (const cand of result.results) {
      if (!map.has(cand.document_id)) map.set(cand.document_id, cand.document_name)
    }
  }
  // Also seed from docList
  for (const doc of knowledgeStore.docList) {
    if (!map.has(doc.id)) map.set(doc.id, doc.name)
  }
  return map
})

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const isHit = computed(() => {
  if (!props.candidate || !props.testCase) return false
  return props.testCase.expected_doc_ids.includes(props.candidate.document_id)
})

const ext = computed(() => {
  if (!props.candidate) return 'pdf'
  const dot = props.candidate.document_name.lastIndexOf('.')
  return dot > -1 ? props.candidate.document_name.slice(dot + 1) : 'pdf'
})

function fmtScore(v: number | null): string {
  return v !== null && v !== undefined ? v.toFixed(4) : '-'
}
</script>

<template>
  <el-drawer
    v-model="visible"
    title="候选明细"
    size="480px"
    :append-to-body="true"
    destroy-on-close
  >
    <template v-if="candidate">
      <div class="hit-badge-row">
        <el-tag :type="isHit ? 'success' : 'info'" size="small">
          {{ isHit ? '命中期望文档' : '未命中期望文档' }}
        </el-tag>
      </div>

      <div class="info-section">
        <h4 class="section-label">文档信息</h4>
        <div class="doc-row">
          <FileIcon :ext="ext" :size="28" />
          <span class="doc-name">{{ candidate.document_name }}</span>
        </div>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-key">章节</span>
            <span class="info-val">{{ candidate.section_path || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="info-key">页码</span>
            <span class="info-val">{{ candidate.page_number }}</span>
          </div>
          <div class="info-item">
            <span class="info-key">字符数</span>
            <span class="info-val">{{ candidate.char_count }}</span>
          </div>
        </div>
      </div>

      <div class="info-section">
        <h4 class="section-label">评分与排名</h4>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="Rank">{{ candidate.rank }}</el-descriptions-item>
          <el-descriptions-item label="向量分">{{ fmtScore(candidate.vector_score) }}</el-descriptions-item>
          <el-descriptions-item label="关键词分">{{ fmtScore(candidate.keyword_score) }}</el-descriptions-item>
          <el-descriptions-item label="向量排名">{{ candidate.vector_rank ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="关键词排名">{{ candidate.keyword_rank ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="RRF">{{ fmtScore(candidate.rrf_score) }}</el-descriptions-item>
          <el-descriptions-item label="Rerank">{{ fmtScore(candidate.rerank_score) }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <div v-if="Object.keys(candidate.metadata).length" class="info-section">
        <h4 class="section-label">元数据</h4>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item
            v-for="(val, key) in candidate.metadata"
            :key="String(key)"
            :label="String(key)"
          >
            {{ typeof val === 'object' ? JSON.stringify(val) : String(val) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <div v-if="testCase && testCase.expected_doc_ids.length" class="info-section">
        <h4 class="section-label">期望文档</h4>
        <div class="expected-list">
          <el-tag
            v-for="docId in testCase.expected_doc_ids"
            :key="docId"
            size="small"
            :type="candidate.document_id === docId ? 'success' : 'info'"
            style="margin: 2px"
          >
            {{ docNameMap.get(docId) || docId }}
          </el-tag>
        </div>
      </div>
    </template>
  </el-drawer>
</template>

<style lang="scss" scoped>
.hit-badge-row {
  margin-bottom: 16px;
}

.info-section {
  margin-bottom: 20px;
}

.section-label {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.doc-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;

  .doc-name {
    font-weight: 500;
    color: #303133;
  }
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.info-item {
  .info-key {
    display: block;
    font-size: 12px;
    color: #909399;
    margin-bottom: 2px;
  }
  .info-val {
    font-size: 14px;
    color: #303133;
  }
}

.expected-list {
  display: flex;
  flex-wrap: wrap;
}
</style>

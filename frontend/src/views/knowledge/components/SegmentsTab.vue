<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import EmptyState from '@/components/common/EmptyState.vue'
import type { Segment } from '@/types/knowledge'

const props = defineProps<{ kbId: string }>()
const knowledgeStore = useKnowledgeStore()

const loading = ref(false)
const expandedRows = ref<string[]>([])
const docFilter = ref('')
const metaDialogVisible = ref(false)
const editingSegment = ref<Segment | null>(null)
const metaForm = ref<Record<string, any>>({})

const chunkMetaFields = computed(() =>
  knowledgeStore.metadataFields.filter(f => f.scope === 'chunk' && f.visible)
)

const docOptions = computed(() => {
  const docs = knowledgeStore.segments.map(s => s.docId)
  return [...new Set(docs)]
})

const filteredSegments = computed(() => {
  if (!docFilter.value) return knowledgeStore.segments
  return knowledgeStore.segments.filter(s => s.docId === docFilter.value)
})

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([
      knowledgeStore.loadSegments(props.kbId),
      knowledgeStore.loadMetadataFields(props.kbId)
    ])
    const parents = knowledgeStore.segments.filter(s => s.type === 'parent' && s.children?.length)
    expandedRows.value = parents.map(s => s.id)
  } finally {
    loading.value = false
  }
})

async function handleToggleStatus(seg: Segment) {
  try {
    await knowledgeStore.updateSegmentStatus(seg.id, seg.enabled)
    ElMessage.success(seg.enabled ? '已启用' : '已禁用')
  } catch {
    seg.enabled = !seg.enabled
    ElMessage.error('操作失败')
  }
}

function openMetaDialog(segment: Segment) {
  editingSegment.value = segment
  const form: Record<string, any> = {}
  for (const f of knowledgeStore.metadataFields.filter(f => f.scope === 'chunk' && f.visible)) {
    const raw = segment.metadata[f.key]
    if (f.dataType === 'number') {
      form[f.key] = raw !== undefined && raw !== '' ? Number(raw) : undefined
    } else if (f.dataType === 'boolean') {
      form[f.key] = raw === 'true'
    } else {
      form[f.key] = raw ?? ''
    }
  }
  metaForm.value = form
  metaDialogVisible.value = true
}

async function saveMeta() {
  if (!editingSegment.value) return
  try {
    const stringData: Record<string, string> = {}
    for (const [k, v] of Object.entries(metaForm.value)) {
      stringData[k] = v === null || v === undefined ? '' : String(v)
    }
    await knowledgeStore.updateSegmentMetadata(editingSegment.value.id, stringData)
    ElMessage.success('元数据保存成功')
    metaDialogVisible.value = false
  } catch {
    ElMessage.error('保存失败')
  }
}

function getDocName(docId: string): string {
  const doc = knowledgeStore.docList.find(d => d.id === docId)
  return doc?.name || docId
}

function getMetaLabel(key: string): string {
  const field = knowledgeStore.metadataFields.find(f => f.key === key)
  return field?.name || key
}
</script>

<template>
  <div v-loading="loading" class="segments-tab">
    <div class="toolbar">
      <el-select v-model="docFilter" placeholder="按文档筛选" clearable style="width: 240px">
        <el-option
          v-for="docId in docOptions"
          :key="docId"
          :label="getDocName(docId)"
          :value="docId"
        />
      </el-select>
      <span class="count-hint">共 {{ filteredSegments.length }} 个分段</span>
    </div>

    <EmptyState
      v-if="!loading && filteredSegments.length === 0"
      icon="Document"
      text="暂无分段数据"
    />

    <el-table
      v-else
      :data="filteredSegments"
      row-key="id"
      :expand-row-keys="expandedRows"
      stripe
      style="width: 100%"
    >
      <el-table-column type="expand" width="40">
        <template #default="{ row }">
          <div class="child-list" v-if="row.children?.length">
            <el-table :data="row.children" border size="small">
              <el-table-column prop="seq" label="#" width="50" />
              <el-table-column label="内容" min-width="300">
                <template #default="{ row: child }">
                  <div class="seg-content">{{ child.content }}</div>
                </template>
              </el-table-column>
              <el-table-column prop="charCount" label="字数" width="70" />
               <el-table-column prop="recallCount" label="召回次数" width="90" />
              <el-table-column label="元数据" width="200">
                <template #default="{ row: child }">
                  <div class="meta-tags" v-if="child.metadata && Object.keys(child.metadata).length">
                    <el-tag v-for="(v, k) in child.metadata" :key="k" size="small" type="info" class="meta-tag">
                      {{ getMetaLabel(String(k)) }}: {{ v }}
                    </el-tag>
                  </div>
                  <span v-else class="text-muted">-</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="80">
                <template #default="{ row: child }">
                  <el-switch
                    v-model="child.enabled"
                    @change="handleToggleStatus(child as Segment)"
                    size="small"
                  />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ row: child }">
                  <el-button text size="small" @click="openMetaDialog(child as Segment)">
                    <el-icon><EditPen /></el-icon>
                  </el-button>
                </template>
              </el-table-column>
              </el-table>
          </div>
          <div v-else class="no-children">无子分段</div>
        </template>
      </el-table-column>

      <el-table-column prop="seq" label="#" width="50" />
      <el-table-column label="文档" width="180">
        <template #default="{ row }">
          <span class="doc-name">{{ getDocName(row.docId) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="row.type === 'parent' ? 'warning' : 'info'">
            {{ row.type === 'parent' ? '父段' : row.type === 'qa' ? 'QA' : '正文' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="内容" min-width="300">
        <template #default="{ row }">
          <div class="seg-content">{{ row.content }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="charCount" label="字数" width="70" />
      <el-table-column prop="recallCount" label="召回次数" width="90" />
      <el-table-column label="元数据" width="200">
        <template #default="{ row }">
          <div class="meta-tags" v-if="Object.keys(row.metadata).length">
            <el-tag v-for="(v, k) in row.metadata" :key="k" size="small" type="info" class="meta-tag">
              {{ getMetaLabel(String(k)) }}: {{ v }}
            </el-tag>
          </div>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-switch
          v-model="row.enabled"
          @change="handleToggleStatus(row as Segment)"
          size="small"
        />
      </template>
    </el-table-column>
    <el-table-column label="操作" width="80">
      <template #default="{ row }">
        <el-button text size="small" @click="openMetaDialog(row as Segment)">
          <el-icon><EditPen /></el-icon>
          <span>元数据</span>
        </el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog v-model="metaDialogVisible" title="编辑分段元数据" width="560px" append-to-body>
    <div v-if="editingSegment" class="meta-dialog-content">
      <div class="seg-preview">
        <span class="seg-preview-label">分段内容：</span>
        <div class="seg-preview-text">{{ editingSegment.content }}</div>
      </div>
      <el-form label-width="120px" label-position="right" style="margin-top: 16px">
        <el-form-item v-if="chunkMetaFields.length === 0">
          <span class="text-muted">该知识库暂无可用的分段元数据字段，请在「元数据」标签页中添加 scope=chunk 的字段。</span>
        </el-form-item>
        <el-form-item
          v-for="field in chunkMetaFields"
          :key="field.id"
          :label="field.name"
        >
          <el-switch
            v-if="field.dataType === 'boolean'"
            v-model="metaForm[field.key]"
          />
          <el-select
            v-else-if="field.dataType === 'select'"
            v-model="metaForm[field.key]"
            placeholder="请选择"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="opt in field.options"
              :key="opt"
              :label="opt"
              :value="opt"
            />
          </el-select>
          <el-date-picker
            v-else-if="field.dataType === 'date'"
            v-model="metaForm[field.key]"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width: 100%"
          />
          <el-input-number
            v-else-if="field.dataType === 'number'"
            v-model="metaForm[field.key]"
            :controls="false"
            style="width: 100%"
          />
          <el-input
            v-else
            v-model="metaForm[field.key]"
            placeholder="请输入"
          />
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="metaDialogVisible = false">取消</el-button>
      <el-button type="primary" @click="saveMeta">保存</el-button>
    </template>
  </el-dialog>
</div>
</template>

<style lang="scss" scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;

  .count-hint {
    font-size: 13px;
    color: #909399;
  }
}

.seg-content {
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.child-list {
  padding: 8px 16px 16px 48px;
}

.no-children {
  padding: 8px 48px;
  color: #909399;
  font-size: 13px;
}

.meta-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;

  .meta-tag {
    margin: 0;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.text-muted {
  color: #c0c4cc;
}

.doc-name {
  font-size: 13px;
  color: #606266;
}

.meta-dialog-content {
  .seg-preview {
    background: #f5f7fa;
    border-radius: 6px;
    padding: 12px;

    .seg-preview-label {
      font-size: 12px;
      color: #909399;
      margin-bottom: 4px;
      display: block;
    }

    .seg-preview-text {
      font-size: 13px;
      color: #606266;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-all;
      max-height: 120px;
      overflow-y: auto;
    }
  }
}
</style>

<script setup lang="ts">
import { computed } from 'vue'
import type { ParentChunk } from '@/types/knowledge'
import FileIcon from '@/components/common/FileIcon.vue'

const props = defineProps<{
  modelValue: boolean
  parentChunk: ParentChunk | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const ext = computed(() => {
  if (!props.parentChunk) return 'pdf'
  const dot = props.parentChunk.document_name.lastIndexOf('.')
  return dot > -1 ? props.parentChunk.document_name.slice(dot + 1) : 'pdf'
})

const levelTag = computed(() => {
  if (!props.parentChunk) return ''
  const levelMap: Record<number, string> = {
    1: '一级标题',
    2: '二级标题',
    3: '三级标题',
  }
  return levelMap[props.parentChunk.level] || `${props.parentChunk.level}级标题`
})

function fmtScore(v: number | null): string {
  return v !== null && v !== undefined ? v.toFixed(4) : '-'
}
</script>

<template>
  <el-drawer
    v-model="visible"
    title="父分段详情"
    size="600px"
    :append-to-body="true"
    destroy-on-close
  >
    <template v-if="parentChunk">
      <div class="parent-chunk-detail">
        <!-- 章节信息 -->
        <div class="info-section">
          <h4 class="section-label">章节信息</h4>
          <div class="title-row">
            <el-tag :type="level === 1 ? 'primary' : 'success'" size="small">
              {{ levelTag }}
            </el-tag>
            <span class="chapter-title">{{ parentChunk.title }}</span>
          </div>
          <div class="doc-row">
            <FileIcon :ext="ext" :size="28" />
            <span class="doc-name">{{ parentChunk.document_name }}</span>
          </div>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-key">子分段数</span>
              <span class="info-val">{{ parentChunk.child_chunk_count }}</span>
            </div>
            <div class="info-item">
              <span class="info-key">检索得分</span>
              <span class="info-val">{{ fmtScore(parentChunk.score) }}</span>
            </div>
            <div class="info-item">
              <span class="info-key">分段模式</span>
              <span class="info-val">{{ parentChunk.parent_chunk_mode }}</span>
            </div>
          </div>
        </div>

        <!-- 父分段完整内容 -->
        <div class="info-section">
          <h4 class="section-label">完整章节内容</h4>
          <div class="content-box parent-content">
            {{ parentChunk.content }}
          </div>
        </div>

        <!-- 命中的子分段 -->
        <div v-if="parentChunk.children.length" class="info-section">
          <h4 class="section-label">
            命中的内容片段
            <el-tag size="small" style="margin-left: 8px">{{ parentChunk.children.length }} 个</el-tag>
          </h4>
          <div class="child-chunks-list">
            <div
              v-for="child in parentChunk.children"
              :key="child.id"
              class="child-chunk-item"
            >
              <div class="child-header">
                <span class="child-position">位置 {{ child.position }}</span>
                <span class="child-score">得分: {{ fmtScore(child.score) }}</span>
              </div>
              <div class="child-content">
                {{ child.content }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </el-drawer>
</template>

<style lang="scss" scoped>
.parent-chunk-detail {
  .info-section {
    margin-bottom: 24px;
  }

  .section-label {
    margin: 0 0 12px;
    font-size: 15px;
    font-weight: 600;
    color: #303133;
    display: flex;
    align-items: center;
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;

    .chapter-title {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
    }
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
    gap: 12px;
  }

  .info-item {
    .info-key {
      display: block;
      font-size: 12px;
      color: #909399;
      margin-bottom: 4px;
    }
    .info-val {
      font-size: 14px;
      color: #303133;
      font-weight: 500;
    }
  }

  .content-box {
    background: #f5f7fa;
    border-radius: 8px;
    padding: 14px;
    font-size: 14px;
    line-height: 1.7;
    color: #303133;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 400px;
    overflow-y: auto;
  }

  .parent-content {
    border-left: 3px solid #409eff;
  }

  .child-chunks-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .child-chunk-item {
    background: #fafafa;
    border-radius: 6px;
    padding: 12px;
    border-left: 2px solid #67c23a;

    .child-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;

      .child-position {
        font-size: 13px;
        font-weight: 600;
        color: #606266;
      }

      .child-score {
        font-size: 12px;
        color: #909399;
      }
    }

    .child-content {
      font-size: 13px;
      line-height: 1.6;
      color: #303133;
      white-space: pre-wrap;
      word-break: break-word;
    }
  }
}
</style>
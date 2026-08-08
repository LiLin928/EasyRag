<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import StatusChip from '@/components/common/StatusChip.vue'
import FileIcon from '@/components/common/FileIcon.vue'
import type { Document } from '@/types/knowledge'

const props = defineProps<{
  kbId: string
}>()

const router = useRouter()
const knowledgeStore = useKnowledgeStore()

const statusMap: Record<string, { type: 'ok' | 'err' | 'warn' | 'run' | 'wait' | 'gray'; label: string }> = {
  done: { type: 'ok', label: '已完成' },
  parsing: { type: 'run', label: '解析中' },
  failed: { type: 'err', label: '失败' },
  pending: { type: 'wait', label: '等待中' }
}

function getStatusInfo(status: string) {
  return statusMap[status] || { type: 'gray', label: status }
}

function handleView(doc: Document) {
  router.push('/knowledge/' + props.kbId + '/docs/' + doc.id)
}

async function handleDelete(doc: Document) {
  try {
    await ElMessageBox.confirm('确定要删除文档"' + doc.name + '"吗？', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await knowledgeStore.deleteDocument(doc.id)
    ElMessage.success('删除成功')
  } catch (error) {
    // 取消删除
  }
}
</script>

<template>
  <el-table :data="knowledgeStore.docList" v-loading="knowledgeStore.docLoading" stripe>
    <el-table-column label="文件名" min-width="200">
      <template #default="{ row }">
        <div class="doc-name">
          <FileIcon :ext="row.ext" :size="32" />
          <span class="name-text">{{ row.name }}</span>
        </div>
      </template>
    </el-table-column>
    
    <el-table-column prop="size" label="大小" width="100" />
    
    <el-table-column label="解析模式" width="100">
      <template #default="{ row }">
        <el-tag size="small" :type="row.mode === 'precision' ? 'warning' : 'info'">
          {{ row.mode === 'precision' ? '精准' : '快速' }}
        </el-tag>
      </template>
    </el-table-column>
    
    <el-table-column label="状态" width="140">
      <template #default="{ row }">
        <div class="status-cell">
          <StatusChip :type="getStatusInfo(row.status).type" :label="getStatusInfo(row.status).label" />
          <el-progress
            v-if="row.status === 'parsing' && row.pct"
            :percentage="row.pct"
            :stroke-width="4"
            :show-text="false"
            style="margin-top: 4px"
          />
        </div>
      </template>
    </el-table-column>
    
    <el-table-column prop="elementCount" label="元素数" width="80" />
    
    <el-table-column prop="createdAt" label="上传时间" width="160" />
    
    <el-table-column label="操作" width="140" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" size="small" @click="handleView(row as Document)">
          详情
        </el-button>
        <el-button link type="danger" size="small" @click="handleDelete(row as Document)">
          删除
        </el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<style lang="scss" scoped>
.doc-name {
  display: flex;
  align-items: center;
  gap: 12px;
  
  .name-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.status-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
</style>


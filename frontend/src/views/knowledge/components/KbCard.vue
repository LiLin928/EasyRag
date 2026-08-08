<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { KnowledgeBase } from '@/types/knowledge'

interface Props {
  data: KnowledgeBase
}

const props = defineProps<Props>()

const emit = defineEmits<{
  edit: [data: KnowledgeBase]
  delete: [id: string]
}>()

const router = useRouter()

function handleClick() {
  router.push('/knowledge/' + props.data.id)
}

function handleEdit(e: Event) {
  e.stopPropagation()
  emit('edit', props.data)
}

function handleDelete(e: Event) {
  e.stopPropagation()
  emit('delete', props.data.id)
}
</script>

<template>
  <div class="kb-card" @click="handleClick">
    <div class="kb-cover" :style="{ backgroundColor: data.cover || '#409eff' }">
      <el-icon :size="48" color="#fff"><Folder /></el-icon>
    </div>
    
    <div class="kb-content">
      <h3 class="kb-name">{{ data.name }}</h3>
      <p class="kb-desc">{{ data.desc }}</p>
      
      <div class="kb-meta">
        <span class="kb-stat">
          <el-icon><Document /></el-icon>
          {{ data.docCount }} 篇文档
        </span>
        <span class="kb-size">{{ data.totalSize }}</span>
      </div>
      
      <el-tag v-if="data.scene" size="small" type="info" class="kb-scene">
        {{ data.scene }}
      </el-tag>
    </div>
    
    <div class="kb-actions" @click.stop>
      <el-dropdown trigger="click">
        <el-icon class="action-icon"><MoreFilled /></el-icon>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="handleEdit">
              <el-icon><Edit /></el-icon>
              编辑
            </el-dropdown-item>
            <el-dropdown-item @click="handleDelete" style="color: #f56c6c">
              <el-icon><Delete /></el-icon>
              删除
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.kb-card {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  position: relative;
  
  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
    
    .kb-actions {
      opacity: 1;
    }
  }
}

.kb-cover {
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.kb-content {
  padding: 16px;
}

.kb-name {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
  height: 40px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.kb-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: #909399;
  
  .kb-stat {
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.kb-scene {
  margin-top: 12px;
}

.kb-actions {
  position: absolute;
  top: 12px;
  right: 12px;
  opacity: 0;
  transition: opacity 0.3s;
  
  .action-icon {
    padding: 4px;
    background: rgba(255, 255, 255, 0.9);
    border-radius: 50%;
    cursor: pointer;
    
    &:hover {
      background: #fff;
    }
  }
}
</style>

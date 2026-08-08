<script setup lang="ts">
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()

// 监听路由变化，添加标签
watch(
  () => route.path,
  (path) => {
    if (route.meta.title) {
      appStore.addTag({
        path,
        title: route.meta.title as string,
        icon: route.meta.icon as string,
        fullPath: route.fullPath
      })
    }
  },
  { immediate: true }
)

function handleClose(path: string) {
  appStore.removeTag(path)
  if (appStore.activeTag === path) {
    const lastTag = appStore.tags[appStore.tags.length - 1]
    if (lastTag) {
      router.push(lastTag.path)
    } else {
      router.push('/')
    }
  }
}

function handleCloseOther() {
  if (appStore.activeTag) {
    appStore.closeOtherTags(appStore.activeTag)
  }
}

function handleCloseAll() {
  appStore.closeAllTags()
  router.push('/')
}
</script>

<template>
  <div class="tags-view" v-if="appStore.tags.length > 0">
    <el-scrollbar>
      <div class="tags-container">
        <el-tag
          v-for="tag in appStore.tags"
          :key="tag.path"
          :closable="appStore.tags.length > 1"
          :effect="tag.path === appStore.activeTag ? 'dark' : 'plain'"
          @close="handleClose(tag.path)"
          @click="router.push(tag.path)"
          class="tag-item"
        >
          <el-icon v-if="tag.icon" class="tag-icon">
            <component :is="tag.icon" />
          </el-icon>
          {{ tag.title }}
        </el-tag>
      </div>
    </el-scrollbar>
    
    <el-dropdown @command="(cmd: string) => cmd === 'other' ? handleCloseOther() : handleCloseAll()">
      <el-icon class="more-icon"><ArrowDown /></el-icon>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="other">关闭其他</el-dropdown-item>
          <el-dropdown-item command="all">关闭所有</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<style lang="scss" scoped>
.tags-view {
  height: 34px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  padding: 0 12px;
  
  :deep(.el-scrollbar) {
    flex: 1;
  }
}

.tags-container {
  display: flex;
  gap: 6px;
  white-space: nowrap;
}

.tag-item {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  
  .tag-icon {
    font-size: 12px;
  }
}

.more-icon {
  margin-left: 8px;
  cursor: pointer;
  color: #606266;
  
  &:hover {
    color: #409eff;
  }
}
</style>

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
        <div
          v-for="tag in appStore.tags"
          :key="tag.path"
          class="tag-item"
          :class="{ active: tag.path === appStore.activeTag }"
          @click="router.push(tag.path)"
        >
          <el-icon v-if="tag.icon" class="tag-icon">
            <component :is="tag.icon" />
          </el-icon>
          <span class="tag-title">{{ tag.title }}</span>
          <el-icon
            v-if="appStore.tags.length > 1"
            class="tag-close"
            @click.stop="handleClose(tag.path)"
          >
            <Close />
          </el-icon>
        </div>
      </div>
    </el-scrollbar>

    <el-dropdown @command="(cmd: string) => cmd === 'other' ? handleCloseOther() : handleCloseAll()">
      <div class="more-btn">
        <el-icon><ArrowDown /></el-icon>
      </div>
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
  height: 40px;
  background: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;

  :deep(.el-scrollbar) {
    flex: 1;
  }
}

.tags-container {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 40px;
  white-space: nowrap;
}

.tag-item {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 12px;
  font-size: 13px;
  color: #606266;
  cursor: pointer;
  border-radius: 6px 6px 0 0;
  transition: background 0.15s ease, color 0.15s ease;
  flex-shrink: 0;

  &:hover {
    background: #f5f7fa;
    color: #303133;

    .tag-close {
      opacity: 1;
    }
  }

  &.active {
    color: var(--el-color-primary, #409eff);
    font-weight: 600;
    background: #fff;

    // 下划线激活条
    &::after {
      content: '';
      position: absolute;
      left: 8px;
      right: 8px;
      bottom: -1px;
      height: 2px;
      background: var(--el-color-primary, #409eff);
      border-radius: 2px;
    }
  }

  .tag-icon {
    font-size: 14px;
  }

  .tag-title {
    line-height: 1;
  }

  .tag-close {
    font-size: 12px;
    border-radius: 50%;
    padding: 1px;
    opacity: 0;
    transition: opacity 0.15s ease, background 0.15s ease, color 0.15s ease;

    &:hover {
      background: rgba(0, 0, 0, 0.08);
      color: #303133;
    }
  }

  // 激活态下关闭按钮常显
  &.active .tag-close {
    opacity: 0.65;
  }
}

.more-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  color: #606266;
  transition: background 0.15s ease, color 0.15s ease;
  flex-shrink: 0;

  &:hover {
    background: #f5f7fa;
    color: var(--el-color-primary, #409eff);
  }
}
</style>

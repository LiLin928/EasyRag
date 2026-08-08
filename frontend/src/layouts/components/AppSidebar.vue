<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const appStore = useAppStore()

// 菜单数据
const menuData = [
  {
    group: '对话中心',
    children: [
      { path: '/chat', title: '智能对话', icon: 'ChatDotRound' }
    ]
  },
  {
    group: '知识库',
    children: [
      { path: '/knowledge', title: '知识库管理', icon: 'Folder' }
    ]
  },
  {
    group: '工作流',
    children: [
      { path: '/workflows', title: '流程列表', icon: 'Share' },
      { path: '/todos', title: '待办中心', icon: 'List' }
    ]
  },
  {
    group: '智能体编排',
    children: [
      { path: '/agents', title: '智能体', icon: 'User' },
      { path: '/tools', title: '工具', icon: 'Tools' },
      { path: '/skills', title: '技能', icon: 'MagicStick' },
      { path: '/mcp', title: 'MCP 服务', icon: 'Connection' }
    ]
  },
  {
    group: '系统设置',
    children: [
      { path: '/settings', title: '系统设置', icon: 'Setting' }
    ]
  }
]

const activeMenu = computed(() => {
  return route.path
})

const isCollapse = computed(() => appStore.sidebarCollapsed)
</script>

<template>
  <el-aside :width="isCollapse ? '64px' : '200px'" class="app-sidebar">
    <el-scrollbar>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
      >
        <template v-for="group in menuData" :key="group.group">
          <el-menu-item-group :title="group.group">
            <el-menu-item
              v-for="item in group.children"
              :key="item.path"
              :index="item.path"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <template #title>{{ item.title }}</template>
            </el-menu-item>
          </el-menu-item-group>
        </template>
      </el-menu>
    </el-scrollbar>
    
    <!-- 折叠按钮 -->
    <div class="collapse-btn" @click="appStore.toggleSidebar">
      <el-icon :size="18">
        <component :is="isCollapse ? 'Expand' : 'Fold'" />
      </el-icon>
    </div>
  </el-aside>
</template>

<style lang="scss" scoped>
.app-sidebar {
  background: #fff;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.05);
  transition: width 0.3s;
  display: flex;
  flex-direction: column;
  
  :deep(.el-menu) {
    border-right: none;
  }
  
  :deep(.el-menu-item) {
    height: 48px;
    line-height: 48px;
    
    &.is-active {
      background: #ecf5ff !important;
      color: #409eff !important;
    }
    
    &:hover {
      background: #ecf5ff !important;
    }
  }
  
  :deep(.el-menu-item-group__title) {
    padding: 12px 0 8px 20px;
    font-size: 12px;
    color: #909399;
  }
}

.collapse-btn {
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-top: 1px solid #e4e7ed;
  color: #606266;
  
  &:hover {
    color: #409eff;
  }
}
</style>

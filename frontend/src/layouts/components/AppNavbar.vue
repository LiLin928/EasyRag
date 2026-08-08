<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppLogo from './AppLogo.vue'

const authStore = useAuthStore()
const router = useRouter()

async function handleCommand(command: string) {
  switch (command) {
    case 'profile':
      // TODO: 跳转个人中心
      break
    case 'settings':
      router.push('/settings')
      break
    case 'logout':
      try {
        await authStore.logout()
        ElMessage.success('已退出登录')
        router.push('/login')
      } catch (error) {
        ElMessage.error('退出失败')
      }
      break
  }
}
</script>

<template>
  <el-header class="app-navbar" height="60px">
    <div class="navbar-left">
      <AppLogo />
    </div>
    
    <div class="navbar-right">
      <!-- 通知徽标 -->
      <el-badge :value="0" :hidden="true">
        <el-icon :size="20" class="nav-icon">
          <Bell />
        </el-icon>
      </el-badge>
      
      <!-- 用户下拉 -->
      <el-dropdown @command="handleCommand">
        <span class="user-dropdown">
          <el-avatar :size="32" :src="authStore.user?.avatar">
            {{ authStore.nickname?.charAt(0) || 'U' }}
          </el-avatar>
          <span class="username">{{ authStore.nickname || '用户' }}</span>
          <el-icon><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              <el-icon><User /></el-icon>
              个人中心
            </el-dropdown-item>
            <el-dropdown-item command="settings">
              <el-icon><Setting /></el-icon>
              设置
            </el-dropdown-item>
            <el-dropdown-item divided command="logout">
              <el-icon><SwitchButton /></el-icon>
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </el-header>
</template>

<style lang="scss" scoped>
.app-navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, #409eff, #66b1ff);
  color: #fff;
  padding: 0 16px;
}

.navbar-left {
  display: flex;
  align-items: center;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.nav-icon {
  color: #fff;
  cursor: pointer;
  
  &:hover {
    opacity: 0.8;
  }
}

.user-dropdown {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #fff;
  
  .username {
    font-size: 14px;
  }
}
</style>

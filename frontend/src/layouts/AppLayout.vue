<script setup lang="ts">
import AppNavbar from './components/AppNavbar.vue'
import AppSidebar from './components/AppSidebar.vue'
import TagsView from './components/TagsView.vue'
</script>

<template>
  <el-container class="app-layout" direction="vertical">
    <!-- 顶栏 -->
    <AppNavbar />
    
    <el-container>
      <!-- 侧边栏 -->
      <AppSidebar />
      
      <el-container direction="vertical">
        <!-- 多页签 -->
        <TagsView />
        
        <!-- 主内容区 -->
        <el-main class="app-main">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </el-container>
</template>

<style lang="scss" scoped>
.app-layout {
  height: 100vh;
  width: 100%;
}

.app-main {
  background: var(--app-content-bg);
  padding: 16px;
  overflow: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

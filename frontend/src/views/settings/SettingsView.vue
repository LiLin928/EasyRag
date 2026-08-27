<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import PageHeader from '@/components/common/PageHeader.vue'
import ModelGroupPanel from './components/ModelGroupPanel.vue'
import ScenePanel from './components/ScenePanel.vue'
import type { ModelGroup } from '@/types/settings'

const settingsStore = useSettingsStore()

const activeTab = ref<string>('llm')

onMounted(() => {
  settingsStore.loadModels()
  settingsStore.loadScenes()
})

function handleTabChange(tab: string) {
  activeTab.value = tab
  if (tab !== 'scenes') {
    settingsStore.activeGroup = tab as ModelGroup
  }
}
</script>

<template>
  <div class="settings-view">
    <PageHeader title="系统设置" subtitle="配置模型参数和场景预设">
      <template #actions>
        <el-button icon="Refresh" @click="settingsStore.loadModels()">
          刷新
        </el-button>
      </template>
    </PageHeader>

    <div class="settings-container">
      <el-menu
        :default-active="activeTab"
        mode="vertical"
        class="settings-nav"
        @select="handleTabChange"
      >
        <el-menu-item index="llm">
          <el-icon><ChatDotRound /></el-icon>
          <span>LLM 模型</span>
        </el-menu-item>
        <el-menu-item index="embed">
          <el-icon><Box /></el-icon>
          <span>Embedding 模型</span>
        </el-menu-item>
        <el-menu-item index="rerank">
          <el-icon><Sort /></el-icon>
          <span>Rerank 模型</span>
        </el-menu-item>
        <el-menu-item index="scenes">
          <el-icon><Grid /></el-icon>
          <span>场景预设</span>
        </el-menu-item>
      </el-menu>

      <div class="settings-content">
        <div v-if="activeTab !== 'scenes'" class="content-section">
          <ModelGroupPanel :group="activeTab as ModelGroup" />
        </div>

        <div v-else class="content-section">
          <ScenePanel />
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.settings-view {
  padding: 0;
}

.settings-container {
  display: flex;
  gap: 20px;
  margin-top: 16px;
}

.settings-nav {
  width: 200px;
}

.settings-content {
  flex: 1;
  min-height: 400px;
}

.content-section {
  animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>

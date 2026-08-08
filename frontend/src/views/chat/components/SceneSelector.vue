<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

onMounted(() => {
  chatStore.loadScenes()
})

function handleChange(scene: string) {
  chatStore.setScene(scene)
}
</script>

<template>
  <el-select
    :model-value="chatStore.activeScene"
    placeholder="选择场景"
    size="default"
    style="width: 120px"
    @change="handleChange"
  >
    <el-option
      v-for="scene in chatStore.scenes"
      :key="scene.id"
      :label="scene.name"
      :value="scene.id"
    />
  </el-select>
</template>

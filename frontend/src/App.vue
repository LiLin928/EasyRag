<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { RouterView } from 'vue-router'
import { useTodoStore } from '@/stores/todo'

const todoStore = useTodoStore()

let countdownInterval: number | null = null

onMounted(() => {
  // 启动全局倒计时每秒更新
  countdownInterval = window.setInterval(() => {
    todoStore.tickCountdown()
  }, 1000)
})

onUnmounted(() => {
  // 清理倒计时定时器
  if (countdownInterval !== null) {
    clearInterval(countdownInterval)
    countdownInterval = null
  }
})
</script>

<template>
  <RouterView />
</template>

<style scoped>
</style>
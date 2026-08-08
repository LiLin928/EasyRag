<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goHome() {
  router.push('/')
}
</script>

<template>
  <div class="app-logo" @click="goHome">
    <el-icon :size="28"><ChatDotRound /></el-icon>
    <span class="logo-text">EasyRAG</span>
  </div>
</template>

<style lang="scss" scoped>
.app-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #fff;
  
  .logo-text {
    font-size: 20px;
    font-weight: 600;
    letter-spacing: 1px;
  }
}
</style>

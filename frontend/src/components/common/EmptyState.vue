<script setup lang="ts">
interface Props {
  icon?: string
  text?: string
}

withDefaults(defineProps<Props>(), {
  icon: 'Folder',
  text: '暂无数据'
})
</script>

<template>
  <div class="empty-state">
    <el-icon :size="64" color="#c0c4cc">
      <component :is="icon" />
    </el-icon>
    <p class="empty-text">{{ text }}</p>
    <div class="empty-action">
      <slot name="action"></slot>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
}

.empty-text {
  color: #909399;
  font-size: 14px;
  margin-top: 16px;
}

.empty-action {
  margin-top: 16px;
}
</style>

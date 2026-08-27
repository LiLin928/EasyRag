<script setup lang="ts">
import { computed } from 'vue'
import StatusChip from '@/components/common/StatusChip.vue'

interface Props {
  seconds: number
}

const props = defineProps<Props>()

// 格式化时间为 HH:MM:SS
const formattedTime = computed(() => {
  const totalSeconds = Math.max(0, props.seconds)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})

// 是否已超时
const isTimeout = computed(() => props.seconds <= 0)
</script>

<template>
  <div v-if="isTimeout" class="countdown-badge timeout">
    <StatusChip type="gray" label="已超时" />
  </div>
  <div v-else class="countdown-badge normal">
    <el-icon><Clock /></el-icon>
    <span>{{ formattedTime }}</span>
  </div>
</template>

<style lang="scss" scoped>
.countdown-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;

  &.normal {
    color: #7C3AED;
    font-size: 13px;
    font-weight: 500;
  }

  &.timeout {
    font-size: 12px;
  }
}
</style>
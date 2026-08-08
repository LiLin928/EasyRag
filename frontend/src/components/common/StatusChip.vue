<script setup lang="ts">
import { computed } from 'vue'

type StatusType = 'ok' | 'err' | 'warn' | 'run' | 'wait' | 'gray'

interface Props {
  type: StatusType
  label?: string
  dot?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  dot: false
})

const statusColors: Record<StatusType, { bg: string; color: string }> = {
  ok: { bg: '#f0fdf4', color: '#16A34A' },
  err: { bg: '#fef2f2', color: '#DC2626' },
  warn: { bg: '#fffbeb', color: '#D97706' },
  run: { bg: '#f0f9ff', color: '#0284C7' },
  wait: { bg: '#faf5ff', color: '#7C3AED' },
  gray: { bg: '#f9fafb', color: '#9ca3af' }
}

const colors = computed(() => statusColors[props.type])
</script>

<template>
  <span
    class="status-chip"
    :style="{
      backgroundColor: colors.bg,
      color: colors.color
    }"
  >
    <span v-if="dot" class="status-dot" :style="{ backgroundColor: colors.color }"></span>
    <span class="status-label">{{ label || type }}</span>
  </span>
</template>

<style lang="scss" scoped>
.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-label {
  line-height: 1.2;
}
</style>

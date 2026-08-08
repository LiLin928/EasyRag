<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useSkillStore } from '@/stores/skill'

interface Props {
  budget?: number
  used?: number
  skillId?: string
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  budget: undefined,
  used: 0,
  skillId: '',
  readonly: false
})

const emit = defineEmits<{
  update: [budget: number]
}>()

const skillStore = useSkillStore()
const editingBudget = ref(false)
const budgetValue = ref(0)

// 计算使用百分比
const percentage = computed(() => {
  if (!props.budget || props.budget === 0) return 0
  return Math.min(100, Math.round(((props.used || 0) / props.budget) * 100))
})

// 计算状态颜色
const progressColor = computed(() => {
  const pct = percentage.value
  if (pct >= 90) return '#DC2626' // 红色警告
  if (pct >= 70) return '#D97706' // 黄色提醒
  return '#16A34A' // 绿色正常
})

// 检查缺失引用
const missingRefs = computed(() => {
  if (!props.skillId) return { tools: [], docs: [], wfs: [] }
  const skill = skillStore.skills.find(s => s.id === props.skillId)
  return skill ? skillStore.missingRefs(skill) : { tools: [], docs: [], wfs: [] }
})

const hasMissingRefs = computed(() => {
  return (
    missingRefs.value.tools.length > 0 ||
    missingRefs.value.docs.length > 0 ||
    missingRefs.value.wfs.length > 0
  )
})

// 监听预算变化
watch(() => props.budget, (newBudget) => {
  budgetValue.value = newBudget || 0
}, { immediate: true })

// 监听预算值变化
watch(budgetValue, (newValue) => {
  emit('update', newValue)
})

function startEdit() {
  if (props.readonly) return
  editingBudget.value = true
}

function finishEdit() {
  editingBudget.value = false
}
</script>

<template>
  <div class="budget-bar">
    <div class="budget-section">
      <div class="section-header">
        <h4>Token 预算</h4>
        <el-button
          v-if="!readonly"
          size="small"
          icon="Edit"
          @click="startEdit"
        >
          {{ budget ? '修改' : '设置' }}
        </el-button>
      </div>

      <div v-if="!editingBudget" class="budget-display">
        <div v-if="budget" class="budget-info">
          <div class="budget-progress">
            <el-progress
              :percentage="percentage"
              :color="progressColor"
              :stroke-width="20"
            />
          </div>
          <div class="budget-text">
            <span class="used">{{ used || 0 }}</span>
            <span class="separator">/</span>
            <span class="total">{{ budget }}</span>
            <span class="unit">Token</span>
          </div>
        </div>
        <div v-else class="no-budget">
          <el-empty description="未设置预算限制" :image-size="60" />
        </div>
      </div>

      <div v-else class="budget-edit">
        <el-input-number
          v-model="budgetValue"
          :min="0"
          :step="1000"
          :precision="0"
          placeholder="请输入预算值"
          style="width: 100%"
        />
        <div class="edit-actions">
          <el-button size="small" @click="editingBudget = false">
            取消
          </el-button>
          <el-button size="small" type="primary" @click="finishEdit">
            确定
          </el-button>
        </div>
      </div>
    </div>

    <div class="refs-section">
      <div class="section-header">
        <h4>资源引用检查</h4>
      </div>

      <div v-if="hasMissingRefs" class="missing-refs">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="发现缺失的资源引用"
        >
          <div class="ref-details">
            <div v-if="missingRefs.tools.length > 0" class="ref-item">
              <strong>缺失工具：</strong>
              <span>{{ missingRefs.tools.join(', ') }}</span>
            </div>
            <div v-if="missingRefs.docs.length > 0" class="ref-item">
              <strong>缺失文档：</strong>
              <span>{{ missingRefs.docs.join(', ') }}</span>
            </div>
            <div v-if="missingRefs.wfs.length > 0" class="ref-item">
              <strong>缺失工作流：</strong>
              <span>{{ missingRefs.wfs.join(', ') }}</span>
            </div>
          </div>
        </el-alert>
      </div>

      <div v-else class="no-missing">
        <el-alert
          type="success"
          :closable="false"
          show-icon
          title="所有资源引用正常"
        />
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.budget-bar {
  padding: 16px;
  height: 100%;
  overflow-y: auto;
}

.budget-section,
.refs-section {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;

  h4 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: #303133;
  }
}

.budget-display {
  .budget-info {
    .budget-progress {
      margin-bottom: 12px;
    }

    .budget-text {
      text-align: center;
      font-size: 16px;
      font-weight: 600;

      .used {
        color: #409eff;
      }

      .separator {
        margin: 0 4px;
        color: #909399;
      }

      .total {
        color: #303133;
      }

      .unit {
        margin-left: 4px;
        font-size: 14px;
        color: #909399;
        font-weight: normal;
      }
    }
  }

  .no-budget {
    padding: 20px 0;
  }
}

.budget-edit {
  .edit-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 12px;
  }
}

.missing-refs,
.no-missing {
  :deep(.el-alert) {
    padding: 12px 16px;
  }
}

.ref-details {
  margin-top: 8px;

  .ref-item {
    margin-bottom: 4px;
    font-size: 13px;

    &:last-child {
      margin-bottom: 0;
    }

    strong {
      color: #D97706;
      margin-right: 8px;
    }

    span {
      color: #606266;
    }
  }
}
</style>

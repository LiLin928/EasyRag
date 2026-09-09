<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useSkillStore } from '@/stores/skill'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import SkillCard from './components/SkillCard.vue'
import SkillConfigDrawer from './components/SkillConfigDrawer.vue'
import type { Skill } from '@/types/skill'

const skillStore = useSkillStore()

const drawerVisible = ref(false)
const editingSkill = ref<Skill | null>(null)

onMounted(() => {
  skillStore.loadSkills()
})

function handleCreate() {
  editingSkill.value = null
  drawerVisible.value = true
}

function handleConfig(skill: Skill) {
  editingSkill.value = skill
  drawerVisible.value = true
}

async function handleDuplicate(id: string) {
  try {
    await skillStore.duplicateSkill(id)
    ElMessage.success('复制成功')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

async function handleDelete(id: string) {
  try {
    await skillStore.deleteSkill(id)
    ElMessage.success('删除成功')
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

async function handleSubmit(data: Partial<Skill>) {
  if (editingSkill.value) {
    await skillStore.updateSkill(editingSkill.value.id, data)
    ElMessage.success('更新成功')
  } else {
    await skillStore.createSkill(data)
    ElMessage.success('创建成功')
  }
}

function handleFilterChange(value: string | number | boolean | undefined) {
  skillStore.filter = value as 'all' | 'builtin' | 'custom'
}
</script>

<template>
  <div class="skills-view">
    <PageHeader title="技能管理" subtitle="管理可复用的能力包，包含触发条件、Prompt SOP 和资源挂载">
      <template #actions>
        <el-input
          v-model="skillStore.keyword"
          placeholder="搜索技能"
          prefix-icon="Search"
          clearable
          style="width: 240px"
        />
        <el-radio-group v-model="skillStore.filter" @change="handleFilterChange">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="builtin">内置</el-radio-button>
          <el-radio-button value="custom">自定义</el-radio-button>
        </el-radio-group>
        <el-button type="primary" icon="Plus" @click="handleCreate">
          新建技能
        </el-button>
      </template>
    </PageHeader>

    <div v-if="skillStore.loading" class="loading-state">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <EmptyState
      v-else-if="skillStore.filteredSkills.length === 0"
      icon="Tools"
      :text="skillStore.keyword ? '未找到匹配的技能' : '暂无技能'"
    >
      <template #action>
        <el-button v-if="!skillStore.keyword" type="primary" @click="handleCreate">
          新建技能
        </el-button>
      </template>
    </EmptyState>

    <div v-else class="skills-grid">
      <SkillCard
        v-for="skill in skillStore.filteredSkills"
        :key="skill.id"
        :data="skill"
        @config="handleConfig"
        @duplicate="handleDuplicate"
        @delete="handleDelete"
      />
    </div>

    <SkillConfigDrawer
      v-model:visible="drawerVisible"
      :data="editingSkill"
      @submit="handleSubmit"
    />
  </div>
</template>

<style lang="scss" scoped>
.skills-view {
  padding: 0;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: #909399;

  p {
    margin-top: 12px;
  }
}

.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-top: 16px;
}
</style>

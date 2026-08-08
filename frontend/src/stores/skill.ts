import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as skillApi from '@/api/skill'
import type { Skill } from '@/types/skill'
import { useToolStore } from './tool'
import { useKnowledgeStore } from './knowledge'
import { useWorkflowListStore } from './workflow'

export const useSkillStore = defineStore('skill', () => {
  // ========== 状态 ==========
  const skills = ref<Skill[]>([])
  const loading = ref(false)
  const filter = ref<'all' | 'builtin' | 'custom'>('all')
  const keyword = ref('')

  // ========== 技能操作 ==========

  async function loadSkills() {
    loading.value = true
    try {
      skills.value = await skillApi.getSkills()
    } finally {
      loading.value = false
    }
  }

  async function loadSkill(id: string) {
    return await skillApi.getSkill(id)
  }

  async function createSkill(data: Partial<Skill>) {
    const skill = await skillApi.createSkill(data)
    skills.value.unshift(skill)
    return skill
  }

  async function updateSkill(id: string, data: Partial<Skill>) {
    const skill = await skillApi.updateSkill(id, data)
    const index = skills.value.findIndex(s => s.id === id)
    if (index > -1) {
      skills.value[index] = skill
    }
    return skill
  }

  async function deleteSkill(id: string) {
    await skillApi.deleteSkill(id)
    skills.value = skills.value.filter(s => s.id !== id)
  }

  async function duplicateSkill(id: string) {
    const skill = await skillApi.duplicateSkill(id)
    skills.value.unshift(skill)
    return skill
  }

  async function setBudget(id: string, budget: number) {
    const skill = await skillApi.updateSkill(id, { budget })
    const index = skills.value.findIndex(s => s.id === id)
    if (index > -1) {
      skills.value[index] = skill
    }
    return skill
  }

  // ========== 计算属性 ==========

  // 过滤后的技能列表
  const filteredSkills = computed(() => {
    let result = skills.value

    // 按范围过滤
    if (filter.value === 'builtin') {
      result = result.filter(s => s.scope === 'builtin')
    } else if (filter.value === 'custom') {
      result = result.filter(s => s.scope === 'custom')
    }

    // 按关键词搜索
    if (keyword.value.trim()) {
      const kw = keyword.value.toLowerCase()
      result = result.filter(s =>
        s.name.toLowerCase().includes(kw) ||
        s.desc.toLowerCase().includes(kw)
      )
    }

    return result
  })

  // 计算挂载数量
  function mountedCount(skill: Skill): number {
    return skill.tools.length + skill.docs.length + skill.wfs.length
  }

  // 检查缺失引用
  function missingRefs(skill: Skill): { tools: string[]; docs: string[]; wfs: string[] } {
    const toolStore = useToolStore()
    const knowledgeStore = useKnowledgeStore()
    const workflowListStore = useWorkflowListStore()

    const missingTools = skill.tools.filter(id =>
      !toolStore.tools.find(t => t.id === id)
    )

    // 从知识库文档中检查
    const allDocs = knowledgeStore.docList
    const missingDocs = skill.docs.filter(id =>
      !allDocs.find(d => d.id === id)
    )

    // 工作流检查
    const missingWfs = skill.wfs.filter(id =>
      !workflowListStore.workflows.find(w => w.id === id)
    )

    return {
      tools: missingTools,
      docs: missingDocs,
      wfs: missingWfs
    }
  }

  // ========== 重置状态 ==========

  function reset() {
    skills.value = []
    loading.value = false
    filter.value = 'all'
    keyword.value = ''
  }

  return {
    // 状态
    skills,
    loading,
    filter,
    keyword,

    // 计算属性
    filteredSkills,

    // 操作
    loadSkills,
    loadSkill,
    createSkill,
    updateSkill,
    deleteSkill,
    duplicateSkill,
    setBudget,

    // 辅助方法
    mountedCount,
    missingRefs,

    // 重置
    reset
  }
})

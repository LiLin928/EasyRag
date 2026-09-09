import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as agentApi from '@/api/agent'
import type { Agent } from '@/types/agent'

export const useAgentStore = defineStore('agent', () => {
  // ========== 状态 ==========
  const agents = ref<Agent[]>([])
  const loading = ref(false)
  const currentAgent = ref<Agent | null>(null)
  const keyword = ref('')

  // ========== 计算属性 ==========

  // 按关键词过滤的智能体列表（名称 / 描述）
  const filteredAgents = computed(() => {
    if (!keyword.value.trim()) return agents.value
    const kw = keyword.value.toLowerCase()
    return agents.value.filter(a =>
      a.name.toLowerCase().includes(kw) ||
      (a.desc || '').toLowerCase().includes(kw)
    )
  })

  // ========== 智能体操作 ==========

  async function loadAgents() {
    loading.value = true
    try {
      agents.value = await agentApi.getAgents()
    } finally {
      loading.value = false
    }
  }

  async function loadAgent(id: string) {
    currentAgent.value = await agentApi.getAgent(id)
    return currentAgent.value
  }

  async function createAgent(data: Partial<Agent>) {
    const agent = await agentApi.createAgent(data)
    agents.value.unshift(agent)
    return agent
  }

  async function updateAgent(id: string, data: Partial<Agent>) {
    const agent = await agentApi.updateAgent(id, data)
    const index = agents.value.findIndex(a => a.id === id)
    if (index > -1) {
      agents.value[index] = agent
    }
    return agent
  }

  async function deleteAgent(id: string) {
    await agentApi.deleteAgent(id)
    agents.value = agents.value.filter(a => a.id !== id)
  }

  async function toggleAgent(id: string, enabled: boolean) {
    const agent = await agentApi.updateAgent(id, { enabled })
    const index = agents.value.findIndex(a => a.id === id)
    if (index > -1) {
      agents.value[index] = agent
    }
    return agent
  }

  // ========== 重置状态 ==========

  function reset() {
    agents.value = []
    currentAgent.value = null
    loading.value = false
    keyword.value = ''
  }

  return {
    // 状态
    agents,
    loading,
    currentAgent,
    keyword,
    filteredAgents,

    // 操作
    loadAgents,
    loadAgent,
    createAgent,
    updateAgent,
    deleteAgent,
    toggleAgent,

    // 重置
    reset
  }
})

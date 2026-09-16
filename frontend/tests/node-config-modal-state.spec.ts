import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import NodeConfigModal from '@/views/workflow/components/NodeConfigModal.vue'

describe('NodeConfigModal - State Reset', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should reset form state when switching between nodes', async () => {
    // 创建 LLM 节点
    const llmNode = {
      id: 'llm-1',
      type: 'llm',
      name: 'LLM 生成',
      position: { x: 100, y: 100 },
      data: {
        config: {
          systemPrompt: '你是一个助手',
          userPrompt: '{{start.query}}',
          temperature: 0.7
        }
      }
    }

    // 创建 RAG 节点
    const ragNode = {
      id: 'rag-1',
      type: 'rag',
      name: 'RAG 检索',
      position: { x: 200, y: 100 },
      data: {
        config: {
          kbIds: [],
          topK: 5
        }
      }
    }

    const wrapper = mount(NodeConfigModal, {
      props: {
        visible: true,
        node: llmNode
      }
    })

    // 验证 LLM 节点配置
    expect(wrapper.vm.form.config.systemPrompt).toBe('你是一个助手')
    expect(wrapper.vm.form.config.userPrompt).toBe('{{start.query}}')
    expect(wrapper.vm.form.config.temperature).toBe(0.7)

    // 切换到 RAG 节点
    await wrapper.setProps({ node: ragNode })

    // 验证 RAG 节点配置，不应该包含 LLM 的配置
    expect(wrapper.vm.form.config.kbIds).toEqual([])
    expect(wrapper.vm.form.config.topK).toBe(5)

    // ✅ 验证 LLM 的配置已被清除
    expect(wrapper.vm.form.config.systemPrompt).toBeUndefined()
    expect(wrapper.vm.form.config.userPrompt).toBeUndefined()
    expect(wrapper.vm.form.config.temperature).toBeUndefined()
  })

  it('should allow adding input variables for LLM node', async () => {
    const llmNode = {
      id: 'llm-1',
      type: 'llm',
      name: 'LLM 生成',
      position: { x: 100, y: 100 },
      data: {
        config: {}
      }
    }

    const wrapper = mount(NodeConfigModal, {
      props: {
        visible: true,
        node: llmNode
      }
    })

    // 初始状态：没有输入变量
    expect(wrapper.vm.form.inputVariables.length).toBe(0)

    // 添加输入变量
    wrapper.vm.addInputVar()

    // 验证：输入变量已添加
    expect(wrapper.vm.form.inputVariables.length).toBe(1)
    expect(wrapper.vm.form.inputVariables[0]).toEqual({ name: '', source: '' })
  })
})
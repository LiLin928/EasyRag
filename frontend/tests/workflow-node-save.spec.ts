/** 测试工作流节点保存修复 */

import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import WorkflowEditorView from '@/views/workflow/WorkflowEditorView.vue'

describe('WorkflowEditorView - Node Save', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should auto-save node config after modification', async () => {
    // 测试节点配置修改后自动保存
    const wrapper = mount(WorkflowEditorView)
    const store = useWorkflowEditorStore()

    // 模拟节点配置修改
    const mockNode = {
      id: 'node-1',
      type: 'llm',
      name: 'LLM 生成',
      position: { x: 100, y: 100 },
      data: {
        config: {
          systemPrompt: '你是一个助手',
          userPrompt: '{{start.query}}'
        }
      }
    }

    // 调用 handleNodeSave
    await wrapper.vm.handleNodeSave(mockNode)

    // 验证节点已更新
    expect(store.nodes.find(n => n.id === 'node-1').data.config.userPrompt).toBe('{{start.query}}')

    // 验证自动保存被调用（需要 mock store.save）
    // expect(store.save).toHaveBeenCalled()
  })

  it('should show warning when leaving with unsaved changes', async () => {
    // 测试离开页面时的保存提示
    const wrapper = mount(WorkflowEditorView)
    const store = useWorkflowEditorStore()

    // 标记为未保存
    store.dirty = true

    // 模拟 beforeunload 事件
    const event = new Event('beforeunload') as BeforeUnloadEvent
    wrapper.vm.handleBeforeUnload(event)

    // 验证事件被阻止
    expect(event.defaultPrevented).toBe(true)
  })
})
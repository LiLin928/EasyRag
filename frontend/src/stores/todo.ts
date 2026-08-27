import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as todoApi from '@/api/todo'
import type { Todo } from '@/types/todo'

export const useTodoStore = defineStore('todo', () => {
  // ========== 状态 ==========
  const todos = ref<Todo[]>([])
  const loading = ref(false)
  const activeTodoId = ref<string | null>(null)

  // ========== 待办操作 ==========

  async function loadTodos(status?: 'pending' | 'done') {
    loading.value = true
    try {
      todos.value = await todoApi.getTodos(status)
    } finally {
      loading.value = false
    }
  }

  async function loadTodo(id: string) {
    const todo = await todoApi.getTodo(id)
    activeTodoId.value = id
    return todo
  }

  async function submitTodo(id: string, formData: Record<string, unknown>) {
    const todo = await todoApi.submitTodo(id, formData)
    const index = todos.value.findIndex(t => t.id === id)
    if (index > -1) {
      todos.value[index] = todo
    }
    return todo
  }

  async function rejectTodo(id: string) {
    const todo = await todoApi.rejectTodo(id)
    const index = todos.value.findIndex(t => t.id === id)
    if (index > -1) {
      todos.value[index] = todo
    }
    return todo
  }

  // 倒计时每秒递减（纯本地状态，不调用 API）
  function tickCountdown() {
    todos.value.forEach(todo => {
      if (todo.status === 'pending' && todo.deadline !== undefined) {
        // 倒计时递减
        todo.deadline = Math.max(0, todo.deadline - 1)

        // 标记超时（不自动改状态）
        if (todo.deadline === 0 && !todo.cd) {
          todo.cd = true
        }
      }
    })
  }

  // ========== 重置状态 ==========

  function reset() {
    todos.value = []
    activeTodoId.value = null
    loading.value = false
  }

  return {
    // 状态
    todos,
    loading,
    activeTodoId,

    // 操作
    loadTodos,
    loadTodo,
    submitTodo,
    rejectTodo,
    tickCountdown,

    // 重置
    reset
  }
})
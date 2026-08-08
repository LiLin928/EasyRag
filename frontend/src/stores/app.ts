import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Tag {
  path: string
  title: string
  icon?: string
  fullPath: string
}

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const tags = ref<Tag[]>([])
  const activeTag = ref<string>('')

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function addTag(tag: Tag) {
    const exists = tags.value.find(t => t.path === tag.path)
    if (!exists) {
      tags.value.push(tag)
    }
    activeTag.value = tag.path
  }

  function removeTag(path: string) {
    const index = tags.value.findIndex(t => t.path === path)
    if (index > -1) {
      tags.value.splice(index, 1)
      if (activeTag.value === path) {
        activeTag.value = tags.value.length > 0 ? tags.value[tags.value.length - 1].path : ''
      }
    }
  }

  function closeOtherTags(path: string) {
    tags.value = tags.value.filter(t => t.path === path)
    activeTag.value = path
  }

  function closeAllTags() {
    tags.value = []
    activeTag.value = ''
  }

  return {
    sidebarCollapsed,
    tags,
    activeTag,
    toggleSidebar,
    addTag,
    removeTag,
    closeOtherTags,
    closeAllTags
  }
})

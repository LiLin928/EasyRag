import { marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import { computed, type ComputedRef } from 'vue'
import 'highlight.js/styles/github.css'

// marked 配置：GFM 表格 + 软换行
marked.setOptions({
  gfm: true,
  breaks: true
})

// 在 DOMPurify 净化流程中对 <pre><code> 代码块做 highlight.js 语法高亮。
// 净化与高亮一步完成，调用方只需 v-html 渲染返回的 HTML。
DOMPurify.addHook('afterSanitizeAttributes', (node: Element) => {
  if (node.tagName === 'CODE' && node.parentElement?.tagName === 'PRE') {
    const text = node.textContent || ''
    if (text.trim()) {
      try {
        node.innerHTML = hljs.highlightAuto(text).value
      } catch {
        // 高亮失败保留原文
      }
    }
  }
})

// 渲染缓存：相同内容不重复 marked + sanitize（流式追加时历史消息命中缓存）
const mdCache = new Map<string, string>()
const MD_CACHE_LIMIT = 500

/**
 * 将 Markdown 文本渲染为经 DOMPurify 净化（+ highlight.js 高亮）的安全 HTML。
 * AGENTS.md §3：输出必须经 DOMPurify 净化。
 */
export function renderMarkdown(content: string): string {
  if (!content) return ''
  const cached = mdCache.get(content)
  if (cached !== undefined) return cached

  const rawHtml = marked.parse(content) as string
  const clean = DOMPurify.sanitize(rawHtml)

  if (mdCache.size >= MD_CACHE_LIMIT) mdCache.clear()
  mdCache.set(content, clean)
  return clean
}

/**
 * 响应式版：传入返回内容字符串的 getter，返回净化 HTML 的 computed。
 */
export function useMarkdown(getContent: () => string): ComputedRef<string> {
  return computed(() => renderMarkdown(getContent()))
}

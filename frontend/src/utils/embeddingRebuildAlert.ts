// Embedding 重建索引确认工具
import { ElMessageBox } from 'element-plus'

interface EmbeddingRebuildAlertOptions {
  title?: string
  content?: string
}

export class EmbeddingRebuildAlertClass {
  static show(options: EmbeddingRebuildAlertOptions = {}): Promise<void> {
    return ElMessageBox.confirm(
      options.content || '切换默认 Embedding 模型需要重建所有向量索引，是否继续？',
      options.title || '重建向量索引确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    ).then(() => {
      // 用户点击确定
    }).catch(() => {
      // 用户点击取消
      throw new Error('用户取消操作')
    })
  }
}

// 导出单例
export const EmbeddingRebuildAlert = EmbeddingRebuildAlertClass

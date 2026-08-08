# 03 · 知识库管理 Knowledge Base（含文档管理 + 文档详情）

> 原型页面：page-documents + page-doc-detail。
> **方案A**：新增「知识库」一层（一个知识库可含多个文档），列表/详情/文档详情合并为一个文件，讲清整条链路。

## 1. 目标

三级结构：**知识库列表 → 知识库详情（文档管理）→ 文档详情（结构树 + 元素浏览）**。
上传文档时必须归属某个知识库；对话的文档选择基于知识库。

## 2. 数据模型（类型 types/knowledge.ts）

```ts
interface KnowledgeBase {
  id: string; name: string; desc: string; scene: string;   // 关联场景预设
  docCount: number; totalSize: string; createdAt: string;
  cover?: string;                                           // 知识库封面色/图
}
interface Document {
  id: string; kbId: string; name: string; ext:'pdf'|'docx'|'md'|...;
  size: string; pages: number; mode:'fast'|'precision'; status:'done'|'parsing'|'failed'|'pending';
  pct?: number; elementCount: number; createdAt: string;
}
interface TreeNode { node_id:string; title:string; level:number; summary?:string|null;
  element_count:number; children:TreeNode[] }
interface DocElement { element_id:string; doc_title:string; type:'text'|'table'|'image'|'heading';
  content:string; node_id:string; node_title:string; page_number:number; seq:number;
  prev_element_id?:string; next_element_id?:string }
```

## 3. 路由

```
/knowledge                       KnowledgeListView    知识库卡片网格
/knowledge/:kbId                 KbDetailView         知识库详情 = 文档管理
/knowledge/:kbId/docs/:docId     DocDetailView        文档详情（结构树 + 元素）
```

## 4. 知识库列表页（KnowledgeListView）

三栏式卡片网格（每卡片：封面色块 + 名称 + 文档数 + 大小 + 场景标签）。右上「新建知识库」按钮。

| 组件 | 路径 | 职责 |
|------|------|------|
| KnowledgeListView | views/knowledge/KnowledgeListView.vue | 页面容器 + 搜索 + 卡片网格 + 空态 |
| KbCard | views/knowledge/components/KbCard.vue | 单卡片：点击进详情；右上菜单（编辑/删除） |
| KbFormDialog | views/knowledge/components/KbFormDialog.vue | 新建/编辑弹窗：名称/描述/场景选择 |

## 5. 知识库详情 / 文档管理（KbDetailView）

顶部：知识库信息条（名称 + 描述 + 场景 + 文档数）。下方文档管理：上传区 + 文档表格（文件名/大小/模式/状态/元素数/时间/操作）。

| 组件 | 路径 | 职责 |
|------|------|------|
| KbDetailView | views/knowledge/KbDetailView.vue | 容器：面包屑 + 信息条 + 上传 + 表格 |
| UploadPanel | views/knowledge/components/UploadPanel.vue | el-upload 拖拽区 + 解析模式(fast/precision) + 场景；上传后轮询状态 |
| DocumentTable | views/knowledge/components/DocumentTable.vue | el-table 文档列表；状态列用 StatusChip；解析中显示进度条；操作：详情/删除 |
| UploadProgressItem | views/knowledge/components/UploadProgressItem.vue | 上传队列项（文件名 + 进度 + 状态） |

**解析状态轮询**：上传返回 task_id，每 2s 轮询 `GET /parse-tasks/{id}`，更新 status/pct；完成停止轮询并刷新列表。

## 6. 文档详情（DocDetailView）

左右分栏：左结构树 + 右元素列表（按章节分组）。结构树高亮"命中"节点（对话引用跳转用）。

| 组件 | 路径 | 职责 |
|------|------|------|
| DocDetailView | views/knowledge/docs/DocDetailView.vue | 容器：文档信息 + 树 + 元素区 |
| TreeBrowser | views/knowledge/docs/TreeBrowser.vue | el-tree 结构树（可折叠），节点显示 element_count；支持定位/高亮 |
| ElementList | views/knowledge/docs/ElementList.vue | 选中章节的元素列表；按类型渲染（text/table/image） |
| ElementCard | views/knowledge/docs/ElementCard.vue | 单元素卡：类型标签 + 内容 + 页码 + 所属章节 |

## 7. Store（stores/knowledge.ts）

```ts
state: { kbList:KnowledgeBase[], currentKb, currentDoc, tree:TreeNode[], elements:DocElement[], uploadQueue }
actions: {
  loadKbList(), createKb(payload), updateKb(id), deleteKb(id)
  loadDocuments(kbId), uploadFiles(kbId, files, mode, scene), deleteDocument(id), pollTask(taskId)
  loadTree(docId), loadElements(docId, {nodeId,type,page})
}
```

## 8. 接口（设计文档 7.x）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST/PUT/DELETE | /knowledge[/:id] | 知识库 CRUD（前端先行，按需补） |
| POST | /documents/upload | 上传（带 kbId + parse_mode + scene） |
| GET | /documents?kb_id= | 文档列表（分页） |
| GET/DELETE | /documents/{id} | 文档详情/删除 |
| GET | /documents/{id}/tree | 结构树 |
| GET | /documents/{id}/elements | 元素列表（按类型/章节） |
| GET | /parse-tasks/{id} | 解析任务状态 |

## 9. Mock 数据

- `mock/knowledge.ts`：3 个知识库（标书库 / 合同库 / 通用库），各含文档（沿用原型 DOCS + 补 kbId）。
- `mock/document.ts`：结构树 TREE、元素列表（text/table 两种）、解析任务进度模拟（轮询时 pct 递增到 100）。

## 10. 实现步骤

1. 类型定义 + Store + Mock。
2. 知识库列表（卡片网格 + 新建弹窗）。
3. 知识库详情（信息条 + UploadPanel + DocumentTable + 轮询）。
4. 文档详情（TreeBrowser + ElementList）。
5. 与对话联动：DocumentPicker（02）从知识库取文档；引用懒加载（02）从元素详情取数据。

## 11. 验收

- [ ] 新建知识库 → 卡片出现。
- [ ] 进知识库 → 上传 PDF → 进度条 → 解析完成 → 列表更新。
- [ ] 文档详情：结构树可展开，选中节点显示该节元素；表格元素渲染为表格。
- [ ] 删除知识库/文档有二次确认。
# 04 · 工作流列表 Workflows（流程/模板/历史）

> 原型页面：page-workflows。三 Tab 列表页，是进入编辑器（05）的入口。

## 1. 目标

单页三 Tab：流程列表（卡片）/ 模板市场（卡片）/ 执行历史（表格）。顶部「新建流程」「从模板创建」入口。

## 2. 组件清单（views/workflow/list/）

| 组件 | 路径 | 职责 |
|------|------|------|
| WorkflowListView | list/WorkflowListView.vue | 容器 + el-tabs(流程/模板/历史) + 顶部操作 |
| WorkflowCard | list/WorkflowCard.vue | 流程卡：图标 + 名称 + 描述 + 状态(草稿/已发布) + 版本 + 最近运行 + 成功率；点击进编辑器 |
| TemplateCard | list/TemplateCard.vue | 模板卡：名称 + 描述 + 标签(官方/社区) + 节点链缩略 + 使用次数；「使用此模板」 |
| ExecutionHistory | list/ExecutionHistory.vue | el-table 执行历史：流程/状态/触发方式/时间/耗时/节点进度(4/7)；行可重跑 |
| WfStatusChip | list/WfStatusChip.vue | 复用 StatusChip：草稿 gray / 已发布 ok / 失败 err / 运行 run |

## 3. 路由

`/workflows` → WorkflowListView；卡片点击 → `/workflows/editor/:id`。

## 4. Store（stores/workflowList.ts）

```ts
state: { workflows:[], templates:[], history:[], activeTab:'list' }
actions: {
  loadWorkflows(), loadTemplates(), loadHistory()
  createWorkflow()       // 新建草稿 → 跳编辑器
  createFromTemplate(tplId)
  deleteWorkflow(id), duplicateWorkflow(id)
}
```

## 5. 接口（设计文档 12.1）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | /workflows | 列表/创建 |
| POST | /workflows/{id}/duplicate | 复制 |
| GET | /templates | 模板列表 |
| POST | /templates/{id}/instantiate | 从模板创建 |
| GET | /executions | 执行历史 |

## 6. Mock（mock/workflow.ts）

- workflows（原型 WFS：标书资质分析/文档摘要/多文档对比，含状态/版本/最近/成功率）。
- templates（原型 TPLS：标书资质审查/文档摘要/合同要素，含节点链+使用次数）。
- history（原型 HIS：含 ok/err/wait 多状态 + 触发方式）。

## 7. 实现步骤

1. 类型 + Store + Mock。
2. 三 Tab 容器 + 空态。
3. WorkflowCard 网格 + 模板/历史 Tab。
4. 卡片操作（编辑/复制/删除/从模板创建）→ 跳转或刷新。

## 8. 验收

- [ ] 三 Tab 切换正常，数据齐全。
- [ ] 新建流程跳编辑器；从模板创建生成草稿。
- [ ] 执行历史显示状态/进度/触发方式。
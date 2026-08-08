# EasyRAG 前端设计方案

> 生成日期：2026-08-03
> 技术栈：Vue 3 (`<script setup>`) + TypeScript + Vite + Pinia + Axios + Element Plus + Vue Flow
> 视觉参考：EasyProject 管理后台（`e-connector.cn/easyproject`）+ 项目原型 `frontend-prototype/`
> 数据现状：前端独立开发，全 Mock，后端后补（接口契约见 `新版RAG需求设计文档_V2*.md`）

---

## 1. 设计目标

把 `frontend-prototype/index.html` 中的 12 个页面，用 Vue 3 全家桶重构成一个可工程化的 SPA。
界面整体风格从原型的「深色顶栏 + 横向导航」改为参考站的 **vue-element-admin 式布局**：蓝色渐变顶栏 + 白色可折叠侧边栏 + 多页签（Tags-View）+ 浅灰内容区。

## 2. 视觉参考分析（来自 EasyProject 实测）

### 2.1 应用外壳（vue-element-admin 风格）

| 部位 | 规格 |
|------|------|
| 顶栏 Navbar | 高 60px，背景 `linear-gradient(135deg,#409eff,#66b1ff)`，左侧白色 Logo+标题，右侧通知徽标 + 用户下拉 |
| 侧边栏 Sidebar | 宽 200px（可折叠至 64px），白色背景 `#fff`，右侧阴影 `2px 0 8px rgba(0,0,0,.05)`，el-menu 分组菜单 |
| 菜单激活态 | 背景 `#ecf5ff`，文字 `#409eff` |
| 多页签 Tags-View | 高 34px，白底，底部 `1px solid #e4e7ed`，浏览器标签页式导航 |
| 内容区 | 背景 `#f5f7fa` |

### 2.2 颜色体系（Element Plus）

```
--el-color-primary      #409eff
--el-text-color-primary #303133
--el-text-color-regular #606266
--el-text-color-secondary #909399
--el-border-color       #dcdfe6
--el-border-color-light #e4e7ed
内容区背景               #f5f7fa
卡片背景                 #ffffff
菜单激活背景             #ecf5ff
```

### 2.3 工作流编辑器（Dify 风格）

| 部位 | 规格 |
|------|------|
| 编辑器顶栏 | 高 56px，白底，底部 `1px solid #e4e7ed`；左：返回 + 流程名 + 状态 + 版本；右：撤销/重做/自动布局/保存/发布 |
| 节点面板 NodePalette | 宽 280px，白底，右侧 `1px solid #e4e7ed`；按分组列出可拖拽节点 |
| 节点项（面板内） | `#f5f7fa` 背景，圆角 8px，232×56，内含 40×40 图标块（`#e6f7ff`）+ 标签(13px) + 类型(11px/#909399) |
| 画布节点卡片 | 浅蓝填充 `#e6f7ff`，描边 `#91d5ff`，圆角 8，约 160×50（运行态按状态染色） |
| 画布 | 可平移/缩放，Vue Flow `dot` 点阵背景 |
| 缩放控件 | 浮动，176×32 |

> 原型 `frontend-prototype` 的工作流编辑器（page-wf-editor）布局与参考站一致，保留原型逻辑、采用参考站配色。

## 3. 页面与路由

```
/login                      登录页（独立，无外壳）
/                           → 重定向 /chat

# ── 对话
/chat                       智能对话
/chat/:conversationId       指定会话

# ── 知识库（新增一层，方案A）
/knowledge                  知识库列表（卡片网格）
/knowledge/:kbId            知识库详情 = 文档管理（上传/列表/状态）
/knowledge/:kbId/docs/:docId 文档详情（结构树 + 元素浏览）

# ── 工作流
/workflows                  工作流列表（流程/模板/历史 三 Tab）
/workflows/editor/:id       工作流编辑器（全屏，无 Tags-View）

# ── 智能体编排
/agents                     智能体
/tools                      工具
/skills                     技能
/mcp                        MCP 服务

# ── 协作与设置
/todos                      待办中心
/settings                   系统设置（模型/场景）
```

> 路由实现：createRouter + beforeEach 鉴权守卫。编辑器页与登录页使用独立 blank 布局，其余用 AppLayout（含 Navbar + Sidebar + TagsView）。

## 4. 目录结构

```
src/
├── api/                      # Axios 模块化接口
│   ├── request.ts            # 实例 + 拦截器（JWT 注入 / 401 刷新）
│   ├── auth.ts  chat.ts  document.ts  knowledge.ts
│   ├── workflow.ts  agent.ts  tool.ts  skill.ts  mcp.ts
│   ├── todo.ts  settings.ts
├── mock/                     # Mock 数据与拦截（开发期）
│   ├── index.ts  chat.ts  document.ts  workflow.ts  ...
├── stores/                   # Pinia
│   ├── auth.ts  app.ts       # 全局
│   ├── chat.ts  doc.ts  knowledge.ts  workflowEditor.ts
│   ├── workflowExecution.ts  workflowList.ts
│   ├── agent.ts  tool.ts  skill.ts  mcp.ts  todo.ts  settings.ts
├── router/
│   ├── index.ts  modules.ts  guard.ts
├── composables/
│   ├── useSSE.ts             # 通用 SSE 封装
│   ├── usePagination.ts  useDialog.ts  useCrud.ts
├── layouts/
│   ├── AppLayout.vue         # Navbar + Sidebar + TagsView + <router-view>
│   ├── components/
│   │   ├── AppNavbar.vue  AppSidebar.vue  TagsView.vue  AppLogo.vue
├── views/                    # 页面（按模块分子目录）
│   ├── login/  chat/  knowledge/  workflow/  agents/  tools/
│   ├── skills/  mcp/  todos/  settings/
├── components/               # 跨模块共享组件
│   ├── common/  StatusChip.vue  FileIcon.vue  EmptyState.vue  PageHeader.vue
├── styles/
│   ├── element-theme.scss    # 参考站配色映射到 Element Plus 变量
│   ├── variables.scss  mixins.scss  index.scss
├── types/                    # 全局 TS 类型
├── utils/                    # 工具
├── App.vue  main.ts
```

## 5. 模块拆分（12 个计划文件）

| 文件 | 模块 | 备注 |
|------|------|------|
| `00-foundation.md` | 基础设施 | 脚手架、Axios、Pinia、Router、Element Plus 主题、SSE、AppLayout（参考站外壳） |
| `01-auth.md` | 登录鉴权 | JWT、路由守卫、登录页 |
| `02-chat.md` | 智能对话 | SSE 流式、分级引用、文档选择、结构树 |
| `03-knowledge-base.md` | 知识库管理 | 知识库列表 + 详情(文档管理) + 文档详情（方案A，合并） |
| `04-workflows.md` | 工作流列表 | 流程/模板/历史 三 Tab |
| `05-workflow-editor.md` | 工作流编辑器 | Vue Flow、12 节点、画布、调试、执行 |
| `06-agents.md` | 智能体 | 卡片 + 配置 + 对话 |
| `07-tools.md` | 工具 | 卡片 + 参数/Auth 配置 |
| `08-skills.md` | 技能 | 卡片 + Prompt/示例/脚本 |
| `09-mcp.md` | MCP | 服务 + 环境变量 + 连通测试 |
| `10-todos.md` | 待办中心 | 人工介入待办 + 动态表单 + 倒计时 |
| `11-settings.md` | 系统设置 | 模型配置(LLM/Embedding/Rerank) + 场景 |

## 6. 跨模块约定

- **接口统一**：`{ code, message, data }`，`code===0` 成功；`code 401xx` 触发刷新。
- **SSE**：对话与工作流执行都用 `@microsoft/fetch-event-source`（框架无关）封装 useSSE。
- **Mock**：开发期用本地 Mock 层（基于设计文档数据结构），后端就绪后切真实接口。
- **共享组件**：StatusChip（映射原型 chip-ok/err/warn/run/wait）、FileIcon、PageHeader、EmptyState。
- **知识库影响**：对话的文档选择、文档管理均下沉到「知识库内」，上传时需选择知识库。

## 7. 实施顺序建议

```
00 基础设施 → 01 登录 → 03 知识库(文档) → 02 对话
→ 04/05 工作流 → 06~09 智能体编排 → 10 待办 → 11 设置
```

理由：基础设施先行；知识库/文档是对话的数据来源，应早于对话；工作流编辑器是独立重型模块；智能体编排依赖工具/技能/MCP；待办依赖工作流；设置最后。
# EasyRAG 前端开发规范（AGENTS.md）

> 适用范围：`frontend/` 目录下的全部代码。本文件面向 AI 编码 Agent，规则均为硬约束；与规则冲突时以本文件为准，并提醒开发者同步修订。

## 1. 工程概况

- EasyRAG 前端是基于 Vue 3 的管理后台 SPA：智能对话（RAG）、知识库、工作流编排、智能体/工具/技能/MCP 编排、待办中心、系统设置。
- 当前阶段：**前端独立开发，全 Mock，后端后补**。
- 实现蓝图：`docs/frontend-plans/`（12 份模块计划）与 `docs/superpowers/specs/2026-08-03-easyrag-frontend-design.md`（总体设计）。动手前先读对应文档。
- `frontend-prototype/` 是只读的视觉与交互参考，禁止修改。

## 2. 目录地图

```
frontend/src/
├── api/            # Axios 模块化接口（request.ts + 每模块一个文件）
├── mock/           # Mock 数据与拦截（index.ts 统一注册）
├── stores/         # Pinia（auth.ts / app.ts 全局 + 每模块一个）
├── router/         # index.ts / modules.ts / guard.ts
├── composables/    # useSSE.ts / usePagination / useDialog / useCrud
├── layouts/        # AppLayout + Navbar/Sidebar/TagsView/Logo；BlankLayout
├── views/          # 页面，按模块分子目录（login/ chat/ knowledge/ workflow/ agents/ tools/ skills/ mcp/ todos/ settings/）
├── components/     # 跨模块共享组件（common/：StatusChip / FileIcon / PageHeader / EmptyState / ConfirmDelete）
├── styles/         # element-theme.scss / variables.scss / mixins.scss / index.scss
├── types/          # 全局 TS 类型（每模块一个文件）
└── utils/
```

- 新增文件必须先在上表中找到归属目录；不允许在 `src/` 根下堆放业务文件。
- 模块私有组件放 `views/<模块>/components/`，跨模块复用才提升到 `src/components/`。

## 3. 技术栈与依赖政策

已定技术栈，禁止替换或平行引入同类库：

- Vue 3（仅 `<script setup lang="ts">`）+ TypeScript + Vite。
- Pinia + `pinia-plugin-persistedstate`（持久化仅限 authStore）。
- Axios；`unplugin-auto-import` + `unplugin-vue-components` 自动导入 Element Plus。
- Vue Router 4；`@vueuse/core`；`sass`。
- SSE 一律用 `@microsoft/fetch-event-source` 封装的 `useSSE`，禁止裸用 EventSource。
- 工作流画布一律用 `@vue-flow/core` + background/controls/minimap。
- Markdown 渲染链路固定：`marked` + `highlight.js` + `dompurify`（输出必须经 DOMPurify 净化）。

新增依赖前必须说明理由与已有依赖无法覆盖的原因；UI 组件只准来自 Element Plus。

## 4. 开发与验证命令

- `npm install`：安装依赖。
- `npm run dev`：本地开发（Mock 开启 `VITE_USE_MOCK=true`，代理 `/api`）。
- `npm run build`：类型检查 + 构建。

验证线（每个模块完成后必须全部通过）：

1. `npm run build` 零错误。
2. `docs/frontend-plans/` 对应模块文档的「验收」清单逐项通过。

本项目未配置 ESLint / Prettier / 单元测试，不要引入，也不要凭空生成相关配置。

## 5. 编码约定

- 组件文件一律 `.vue` 单文件组件；禁止用 `.ts` 文件承载组件（计划文档中个别 `.ts` 组件条目是笔误，按 `.vue` 实现）。
- 纯逻辑（流式追加、格式化、请求辅助）放 `composables/`（use 前缀）或 `utils/` 的 `.ts`。
- 文件命名：组件与视图 `PascalCase.vue`（页面级以 `View` 结尾，如 `ChatView.vue`）；store / api / mock / types 小写 `kebab` 或单词（如 `stores/chat.ts`、`types/chat.ts`、`mock/chat.ts`）。
- 类型集中在 `types/<模块>.ts`，接口响应、SSE 事件、组件 Props 都必须有显式类型，禁止 `any` 兜底业务字段。
- Store 每模块一个文件；token 等持久化状态仅经 `pinia-plugin-persistedstate`，禁止散落 `localStorage` 直写。
- 所有 HTTP 请求只准走 `api/request.ts` 实例：自动注入 `Authorization: Bearer`；`code===0` 解包 `data`；`40100-40199` 经 refresh_token 刷新后重试（并发请求排队，禁止并发刷新）；其余 `code` 走 `ElMessage.error`。
- 路由在 `router/modules.ts` 按模块拆分，`meta` 必须声明 `{ title, icon, requiresAuth }`；受保护路由由 `router/guard.ts` 统一守卫，白名单仅 `/login`。
- 布局：业务页挂 `AppLayout`；`/login` 与 `/workflows/editor/:id` 用 `BlankLayout`。
- 通用交互必须复用共享组件：状态徽标用 `StatusChip`（ok/err/warn/run/wait/gray）、文件图标用 `FileIcon`、页面标题栏用 `PageHeader`、空态用 `EmptyState`、删除操作必须经 `ConfirmDelete` 二次确认。

## 6. Mock 先行规则

- 后端补全之前，所有接口一律走 Mock；不允许出现"等后端"而留空的页面逻辑。
- Mock 数据放 `mock/<模块>.ts`，在 `mock/index.ts` 统一注册；由 `VITE_USE_MOCK=true` 开关控制。
- Mock 的数据结构、字段名、SSE 事件顺序必须严格符合接口契约：`docs/新版RAG需求设计文档_V2.md`、`docs/新版RAG需求设计文档_V2_workflow.md`，以及各计划文档的接口表。禁止自造字段、改事件名、改事件顺序。
- 契约没有的接口不准实现、也不准 Mock；发现契约缺口时先在计划文档标注，再与开发者确认。
- SSE 类接口（对话、工作流执行、解析任务）必须提供定时器 Mock 模拟器，按契约事件顺序 emit。
- `api/` 层只写真接口签名，禁止掺入 Mock 分支；Mock 拦截发生在 request 层或 vite 插件层，保证后端就绪后关闭开关即可切换。

## 7. SSE 约定

- 对话（02）与工作流执行（05）共用 `composables/useSSE.ts`：`useSSE(url, { body, onEvent, signal })`，支持 POST + 自定义 headers + 按事件类型分发。
- 对话事件顺序：`phase(parse) → phase(navigate) → navigation → phase(retrieve) → references → phase(generate) → token... → done → trace`。
- 工作流执行事件顺序：`execution_start → node_start → node_progress → node_complete（可含 node_error/retry、execution_paused/resumed）→ execution_complete | execution_error`。
- 必须处理 `event:error`；流组件必须支持 `AbortController` 中断与组件卸载清理。

## 8. 样式约定

- 颜色、圆角、阴影只准取自 `styles/element-theme.scss` 与 `styles/variables.scss` 定义的变量（CSS 变量或 SCSS 变量），禁止在组件里硬编码新的色值。
- 主色 `#409eff`，状态色 `$ok #16A34A / $err #DC2626 / $warn #D97706 / $run #0284C7 / $wait #7C3AED`。
- 外壳规格固定：顶栏 60px 蓝渐变（`linear-gradient(135deg,#409eff,#66b1ff)`）、侧边栏 200px 可折叠至 64px、多页签 34px、内容区背景 `#f5f7fa`、菜单激活态 `#ecf5ff/#409eff`。
- 工作流编辑器为 Dify 风格：56px 白顶栏、280px 节点面板、节点卡浅蓝 `#e6f7ff` 描边 `#91d5ff`、Vue Flow 点阵背景。

## 9. 实施顺序与验收流程

- 模块实现必须按此顺序（依赖关系决定，不许跳）：

```
00 基础设施 → 01 登录 → 03 知识库(含文档) → 02 对话
→ 04/05 工作流 → 06~09 智能体编排 → 10 待办 → 11 设置
```

- 每个模块的交付物 = 计划文档中的：类型 + Store + Mock + 组件 + 接口层，缺一不可。
- 模块完成判定：`npm run build` 零错误 + 该模块「验收」清单逐项通过；未完成不得开始下一模块。

## 10. 模块索引

| # | 模块 | 计划文档 | 关键能力 |
|---|------|----------|----------|
| 00 | 基础设施 | [00-foundation.md](../docs/frontend-plans/00-foundation.md) | 工程骨架、Element Plus 主题、Axios/Pinia/Router、AppLayout 外壳、useSSE、Mock 层 |
| 01 | 登录鉴权 | [01-auth.md](../docs/frontend-plans/01-auth.md) | JWT、路由守卫、自动刷新 |
| 02 | 智能对话 | [02-chat.md](../docs/frontend-plans/02-chat.md) | SSE 流式、四阶段指示器、分级引用、文档选择 |
| 03 | 知识库管理 | [03-knowledge-base.md](../docs/frontend-plans/03-knowledge-base.md) | 知识库→文档→文档详情三级、上传解析轮询 |
| 04 | 工作流列表 | [04-workflows.md](../docs/frontend-plans/04-workflows.md) | 流程/模板/历史三 Tab |
| 05 | 工作流编辑器 | [05-workflow-editor.md](../docs/frontend-plans/05-workflow-editor.md) | Vue Flow、12 节点、执行 SSE 染色、单步调试 |
| 06 | 智能体 | [06-agents.md](../docs/frontend-plans/06-agents.md) | 卡片 + 配置抽屉 + 能力挂载 + 对话 |
| 07 | 工具 | [07-tools.md](../docs/frontend-plans/07-tools.md) | 卡片 + 参数/Auth 配置 + 连通测试 |
| 08 | 技能 | [08-skills.md](../docs/frontend-plans/08-skills.md) | 卡片 + Prompt/示例/脚本/挂载 + 预算 |
| 09 | MCP | [09-mcp.md](../docs/frontend-plans/09-mcp.md) | 服务 + 环境变量 + 连通测试 |
| 10 | 待办中心 | [10-todos.md](../docs/frontend-plans/10-todos.md) | 人工介入待办 + 动态表单 + 倒计时 |
| 11 | 系统设置 | [11-settings.md](../docs/frontend-plans/11-settings.md) | 模型配置（LLM/Embedding/Rerank）+ 场景预设 |

## 11. 文档参考优先级

1. 本文件（硬约束，冲突时以此为准）。
2. `docs/frontend-plans/<模块>.md`（组件清单、Store、接口、Mock、验收）。
3. `docs/superpowers/specs/2026-08-03-easyrag-frontend-design.md`（总体设计与视觉规格）。
4. `docs/新版RAG需求设计文档_V2*.md`（接口契约的最终依据）。
5. `frontend-prototype/index.html`（视觉/交互参考，只读）。

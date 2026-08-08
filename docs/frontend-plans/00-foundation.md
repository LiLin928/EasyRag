# 00 · 基础设施 Foundation

> 所有模块的地基。先于业务模块实现。视觉遵循 EasyProject 参考（vue-element-admin 风格）。

## 1. 目标

搭建 Vue 3 + TS + Vite 工程骨架，配置 Element Plus（参考站配色）、Pinia、Axios（JWT 拦截）、Vue Router（守卫）、SSE 工具、Mock 层、以及应用外壳 AppLayout（蓝色渐变顶栏 + 白色可折叠侧边栏 + Tags-View 多页签）。

## 2. 工程初始化

```bash
npm create vite@latest . -- --template vue-ts
# 依赖
npm i element-plus @element-plus/icons-vue pinia pinia-plugin-persistedstate axios
npm i vue-router@4 @vueuse/core @microsoft/fetch-event-source
npm i @vue-flow/core @vue-flow/background @vue-flow/controls @vue-flow/minimap   # 工作流用
npm i marked highlight.js dompurify                                              # Markdown 渲染
npm i -D unplugin-auto-import unplugin-vue-components sass @types/node
```

`vite.config.ts`：自动导入 Element Plus、`@` 别名 → `src`、dev 代理 `/api` → 后端。

## 3. 组件清单

### 3.1 布局组件（layouts/）

| 组件 | 路径 | 职责 |
|------|------|------|
| AppLayout | layouts/AppLayout.vue | 整体外壳容器：`el-container` 垂直布局，承载 Navbar + (Sidebar + TagsView + router-view) |
| AppNavbar | layouts/components/AppNavbar.vue | 60px 蓝色渐变顶栏；左：AppLogo；右：通知徽标(el-badge) + 用户下拉(el-dropdown) |
| AppSidebar | layouts/components/AppSidebar.vue | 200px 白色侧边栏，el-menu 分组菜单，支持折叠（64px），激活态 `#ecf5ff`/`#409eff` |
| TagsView | layouts/components/TagsView.vue | 34px 多页签，跟随路由渲染标签，可关闭/右键关闭其它/全部；持久化已开标签 |
| AppLogo | layouts/components/AppLogo.vue | Logo 图标 + 系统名（EasyRAG），白色文字 |
| BlankLayout | layouts/BlankLayout.vue | 空布局（登录页、工作流编辑器用） |

### 3.2 侧边栏菜单结构（按业务分组）

```
对话中心
  └ 智能对话               /chat
知识库
  └ 知识库管理             /knowledge
工作流
  ├ 流程列表               /workflows
  └ 待办中心               /todos
智能体编排
  ├ 智能体                 /agents
  ├ 工具                   /tools
  ├ 技能                   /skills
  └ MCP 服务               /mcp
系统设置                   /settings
```

### 3.3 共享组件（components/common/）

| 组件 | 职责 | 关键 Props |
|------|------|-----------|
| StatusChip | 状态徽标（映射原型 ok/err/warn/run/wait/gray） | `type:'ok'|'err'|'warn'|'run'|'wait'|'gray'`, `label`, `dot?` |
| FileIcon | 文件类型图标块（PDF/DOC/MD…，按扩展名配色） | `ext:string` |
| PageHeader | 页面标题栏（标题 + 副标题 + 右侧操作槽） | `title`,`subtitle`, slot `actions` |
| EmptyState | 空状态占位 | `icon`,`text`,`action?` |
| ConfirmDelete | 二次确认删除按钮（el-popconfirm） | `onConfirm` |

## 4. 设计系统（styles/）

### element-theme.scss —— 把参考站配色注入 Element Plus

```scss
:root {
  --el-color-primary: #409eff;
  --el-color-primary-light-3: #66b1ff;
  --el-color-primary-light-9: #ecf5ff;
  --el-text-color-primary: #303133;
  --el-text-color-regular: #606266;
  --el-text-color-secondary: #909399;
  --el-border-color: #dcdfe6;
  --el-border-color-light: #e4e7ed;
  --app-content-bg: #f5f7fa;
  --app-navbar-grad: linear-gradient(135deg, #409eff, #66b1ff);
}
// 顶栏渐变
.app-navbar { background: var(--app-navbar-grad); }
// 菜单激活态
.el-menu-item.is-active { background: #ecf5ff; color: #409eff; }
```

### variables.scss / mixins.scss
状态色（来自原型）：`$ok #16A34A $err #DC2626 $warn #D97706 $run #0284C7 $wait #7C3AED`；圆角 `$r-sm 6px $r 8px $r-lg 12px`；阴影 `$sh-1/$sh-2/$sh-3`。

## 5. Axios 封装（api/request.ts）

- 拦截器注入 `Authorization: Bearer <token>`（从 authStore）。
- 响应拦截：`code===0` 返回 `data`；`40100-40199` → 用 refresh_token 刷新后重试（队列等待，避免并发刷新）；其余 `code` 走 ElMessage.error。
- 环境变量 `VITE_API_BASE=/api/v2`。

## 6. Pinia 全局 Store

### authStore（stores/auth.ts）
```ts
state: { token, refreshToken, user }   // persisted
actions: { login, logout, refresh, getUserInfo }
```
### appStore（stores/app.ts）
```ts
state: { sidebarCollapsed, tags[], activeTag }  // 侧边栏折叠、页签状态
actions: { toggleSidebar, addTag, removeTag, closeOtherTags }
```

## 7. Router（router/）

- `modules.ts`：按模块拆分路由配置；meta 声明 `{ title, icon, requiresAuth }`。
- `guard.ts`：`beforeEach` —— 无 token 且非白名单 → 跳 `/login`；根据 to.meta.title 驱动 TagsView 与文档标题。
- 布局路由：`AppLayout` 为父路由，业务页为 children；`/login`、`/workflows/editor/:id` 用 `BlankLayout`。

## 8. SSE 工具（composables/useSSE.ts）

封装 `@microsoft/fetch-event-source`，支持 POST + 自定义 headers + 事件分发：
```ts
useSSE(url, { body, onEvent: (type, data) => void, signal })
```
对话模块（02）和工作流执行（05）共用。

## 9. Mock 层（mock/）

开发期拦截 `request.ts` 或用 vite 插件，按模块返回设计文档中的数据结构（CONVS/DOCS/NODES/AGENTS/TOOLS/SKILLS/MCPS…）。每个模块计划含自己的 mock 片段，统一在此注册。提供开关：`VITE_USE_MOCK=true`。

## 10. 实现步骤

1. Vite 脚手架 + 依赖 + 别名 + 自动导入。
2. styles 设计系统 + element-theme.scss（参考站配色）。
3. AppLayout + Navbar + Sidebar + TagsView（核心外壳，参考站实测尺寸）。
4. Axios request.ts + 拦截器 + authStore/appStore。
5. Router + guard。
6. useSSE + Mock 框架。
7. 共享组件 StatusChip/FileIcon/PageHeader/EmptyState。
8. 验证：能进入空外壳、侧边栏菜单可点、页签随路由开合、登录跳转守卫生效。

## 11. 验收

- [ ] 应用呈现参考站布局（蓝渐变顶栏 + 白侧栏 + 多页签 + 浅灰内容）。
- [ ] 侧边栏菜单分组完整，可折叠，激活态正确。
- [ ] 未登录访问受保护页 → 跳登录。
- [ ] Axios 自动带 token，401 触发刷新。
- [ ] useSSE 可建立流并分发事件。
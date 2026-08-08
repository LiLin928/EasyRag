# EasyRAG 前端模块计划（索引）

> 技术栈：Vue 3 + TypeScript + Vite + Pinia + Axios + Element Plus + Vue Flow
> 视觉参考：EasyProject 管理后台（vue-element-admin 风格）+ `frontend-prototype/`
> 总体设计：见 `../superpowers/specs/2026-08-03-easyrag-frontend-design.md`
> 数据：前端全 Mock，后端后补（接口契约见 `新版RAG需求设计文档_V2*.md`）

## 模块清单与实施顺序

| 序 | 文件 | 模块 | 对应原型 | 关键能力 |
|----|------|------|---------|---------|
| 0 | [00-foundation.md](00-foundation.md) | 基础设施 | 全局 | 工程骨架、Element Plus 主题、Axios/Pinia/Router、AppLayout(蓝顶栏+白侧栏+多页签)、useSSE、Mock 层 |
| 1 | [01-auth.md](01-auth.md) | 登录鉴权 | page-login | JWT、路由守卫、登录页、自动刷新 |
| 2 | [02-chat.md](02-chat.md) | 智能对话 | page-chat | SSE 流式、四阶段指示、分级引用、文档选择、结构树 |
| 3 | [03-knowledge-base.md](03-knowledge-base.md) | 知识库管理 | page-documents + page-doc-detail | **知识库→文档→文档详情**（方案A） |
| 4 | [04-workflows.md](04-workflows.md) | 工作流列表 | page-workflows | 流程/模板/历史 三 Tab |
| 5 | [05-workflow-editor.md](05-workflow-editor.md) | 工作流编辑器 | page-wf-editor | Vue Flow、12 节点、画布、调试、执行 SSE |
| 6 | [06-agents.md](06-agents.md) | 智能体 | page-agents | 卡片+配置抽屉+对话 |
| 7 | [07-tools.md](07-tools.md) | 工具 | page-tools | 卡片+参数/Auth 配置+测试 |
| 8 | [08-skills.md](08-skills.md) | 技能 | page-skills | 卡片+Prompt/示例/脚本/挂载 |
| 9 | [09-mcp.md](09-mcp.md) | MCP | page-mcp | 服务+环境变量+连通测试 |
| 10 | [10-todos.md](10-todos.md) | 待办中心 | page-todos | 人工介入待办+动态表单+倒计时 |
| 11 | [11-settings.md](11-settings.md) | 系统设置 | page-settings | 模型配置(LLM/Embedding/Rerank)+场景 |

## 建议实施顺序

```
00 基础设施 → 01 登录 → 03 知识库(文档) → 02 对话
→ 04/05 工作流 → 06~09 智能体编排 → 10 待办 → 11 设置
```

## 每个计划文件包含

模块概述 · 对应原型/参考 · 路由 · **组件清单(职责/Props/Events)** · Pinia Store · 接口(含 Mock 数据) · 实现步骤 · 验收清单

## 知识库变更说明（相对原型）

原型文档管理升级为 **知识库 → 文档** 两层：上传文档须归属知识库；对话的文档选择基于知识库。详见 `03-knowledge-base.md`。
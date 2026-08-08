# 08 · 技能 Skills

> 原型页面：page-skills。封装「触发条件 + Prompt SOP + 工具/文档/工作流挂载 + 示例 + 脚本」的可复用能力包。

## 1. 目标

卡片网格（区分内置 builtin / 自定义 custom）；配置抽屉含多 Tab（基础/示例/脚本/挂载）；技能预算（Token 限额）与缺失引用检测。

## 2. 组件清单（views/skills/）

| 组件 | 路径 | 职责 |
|------|------|------|
| SkillsView | SkillsView.vue | 容器 + 搜索 + 过滤(全部/内置/自定义) + 「新建技能」+ 卡片网格 |
| SkillCard | components/SkillCard.vue | 卡片：图标 + 名称 + 范围徽标(内置/自定义) + 版本 + 描述；统计(示例数/挂载数)；操作（配置/复制/删除） |
| SkillConfigDrawer | components/SkillConfigDrawer.ts | el-drawer，含 el-tabs： |
| └ SkillBasicTab | components/SkillBasicTab.vue | 名称/图标/描述/触发条件/系统 Prompt |
| └ SkillExamplesTab | components/SkillExamplesTab.vue | 问答示例对（动态增删 q/a） |
| └ SkillScriptsTab | components/SkillScriptsTab.vue | 关联脚本列表（增删 + 顺序） |
| └ SkillMountsTab | components/SkillMountsTab.vue | 挂载工具/文档/工作流（多选） |
| SkillBudgetBar | components/SkillBudgetBar.vue | 技能 Token 预算与已用进度；缺失引用提示 |

## 3. 数据模型（types/skill.ts）
```ts
interface Skill { id:string; ico:string; name:string; scope:'builtin'|'custom'; ver:string;
  desc:string; trigger:string; prompt:string;
  tools:string[]; docs:string[]; wfs:string[];
  examples:{q:string;a:string}[]; scripts:{name:string}[];
  budget?:number; used?:number }
```

## 4. Store（stores/skill.ts）：CRUD + 过滤/搜索 + mountedCount/missingRefs 计算 + setBudget。

## 5. Mock（mock/skill.ts）：原型 SKILLS（标书资质审查 SOP/合同风险清单/研报摘要规范/客服升级流程，含 examples/scripts）。

## 6. 实现步骤
1. 类型 + Store + Mock。2. 卡片网格 + 过滤搜索。3. 配置抽屉四 Tab。4. 预算条 + 缺失引用检测。

## 7. 验收
- [ ] 新建/编辑/复制/删除技能；内置技能不可删（只读或复制为自定义）。
- [ ] 四 Tab 完整：示例动态增删、脚本顺序、挂载多选、预算可设。
- [ ] 缺失引用（已删工具/文档）有提示。
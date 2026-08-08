# 07 · 工具 Tools

> 原型页面：page-tools。可被智能体/工作流调用的外部能力（HTTP/内置/Python）。

## 1. 目标

卡片网格；配置弹窗含参数定义 + 鉴权；启用/停用；连通测试。

## 2. 组件清单（views/tools/）

| 组件 | 路径 | 职责 |
|------|------|------|
| ToolsView | ToolsView.vue | 容器 + 「新建工具」+ 卡片网格 |
| ToolCard | components/ToolCard.vue | 卡片：类型徽标(HTTP/内置/Python) + 名称 + 签名(monospace) + 启停开关；操作（配置/测试/删除） |
| ToolConfigDialog | components/ToolConfigDialog.vue | el-dialog：名称/类型/描述 + 签名 + 参数表(动态行 name/type/default) + 鉴权(none/apikey/bearer) |
| ToolTestPanel | components/ToolTestPanel.vue | 填测试参数 → 执行 → 展示返回（Mock 模拟延迟与结果） |

## 3. 数据模型（types/tool.ts）
```ts
interface Tool { id:string; name:string; type:'HTTP'|'内置'|'Python'; desc:string; sig:string;
  enabled:boolean; params:{n:string;t:string;d:string}[]; auth:{mode:'none'|'apikey'|'bearer'; key:string} }
```

## 4. Store（stores/tool.ts）：CRUD + toggle + testTool(id, args)。

## 5. Mock（mock/tool.ts）：原型 TOOLS（天气查询/只读 SQL/邮件通知/数据换算，含参数与鉴权）。

## 6. 实现步骤
1. 类型 + Store + Mock。2. 卡片网格 + 启停。3. 配置弹窗（动态参数行 + 鉴权）。4. 测试面板。

## 7. 验收
- [ ] 新建/编辑/删除/启停工具；动态增删参数；保存鉴权（密钥掩码）。
- [ ] 测试执行返回模拟结果。